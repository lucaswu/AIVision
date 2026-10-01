"""共享的 TensorRT engine 构建 / 缓存 / 加载工具。

背景：TensorRT engine 是和具体GPU型号(compute capability)、驱动、TensorRT版本绑定的
二进制产物，不能像 .pt/.pth 权重那样在开发机编译好直接分发到客户现场的不同硬件上。
因此这里的策略是"懒构建 + 持久化缓存 + 后台异步升级"：

- 每个模型第一次被实例化时，检查是否已经有一份匹配当前 GPU/TensorRT 版本、且和源权重
  文件一致的 engine 缓存；命中就直接加载，和原来一样快。
- 没命中（新权重、新硬件，或者第一次冷启动）时，**不会同步阻塞等构建**：立即返回一个
  包着 PyTorch 权重的可热替换代理对象，让调用方（无论是容器冷启动的bootstrap，还是
  model-agent 触发的模型热切换 prepare()）马上能往下走，不会被TensorRT构建耗时卡住。
  真正的构建被丢进一个全局单线程后台队列，构建成功后原地把代理对象内部换成
  TensorRT engine——这之后发生的推理调用自动就走上了加速路径，调用方完全不用感知
  这个切换过程。
  这个设计是从一次真实的运维风险推出来的：model-agent 调用 ai-inference 内部的
  /internal/runtime/prepare 接口设了600秒超时，而 prepare() 内部同步构建模型（见
  model_runtime_manager.py）；如果同一次模型发布换了多个slot（比如RF-DETR+3个YOLO
  一起换），同步构建的总耗时很容易超过600秒，导致 model-agent 误判这次发布失败——
  即使 ai-inference 这边其实最终会构建成功。改成异步后台升级后，prepare() 本身只
  等 PyTorch 权重加载完就返回，彻底不会被TensorRT构建拖慢。
- 任何环节（TensorRT 未安装、构建失败、engine 加载失败）都必须安全回退到原始 PyTorch
  路径，绝不能因为 TensorRT 相关问题导致推理服务整体起不来。
- 通过环境变量 INFERENCE_USE_TENSORRT 控制总开关，默认开启。
"""

from __future__ import annotations

import concurrent.futures
import ctypes
import hashlib
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

_LOCKS: Dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_CUDART_FIX_DONE = False
# torch.onnx.export（以及ultralytics内部调用的同一套导出逻辑）不是线程安全的：
# 两个导出同时跑会互相污染内部的tracer/符号表状态，表现为其中一个诡异地瞬间失败
# 且异常信息是空的。下面的后台构建队列本身是单线程、天然串行的，但这把锁留着当
# 双重保险（万一将来有代码不经过队列、直接调用构建函数）。
_EXPORT_SERIALIZE_LOCK = threading.Lock()

# 所有 TensorRT engine 的现场构建都丢进这一个单线程队列：天然串行执行，不会有
# 多个大模型同时抢GPU显存/算力互相拖慢，也省掉了额外的并发控制。
_BACKGROUND_EXECUTOR: Optional["concurrent.futures.ThreadPoolExecutor"] = None
_BACKGROUND_EXECUTOR_GUARD = threading.Lock()


def _background_executor() -> "concurrent.futures.ThreadPoolExecutor":
    global _BACKGROUND_EXECUTOR
    with _BACKGROUND_EXECUTOR_GUARD:
        if _BACKGROUND_EXECUTOR is None:
            _BACKGROUND_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="trt-build"
            )
        return _BACKGROUND_EXECUTOR


def _submit_background(fn: Callable[[], None]) -> None:
    def _run() -> None:
        try:
            fn()
        except Exception as exc:  # 后台任务的异常绝不能冒出去影响别的请求
            print(f"[trt_backend] 后台构建任务异常(已忽略，继续用PyTorch): {str(exc) or repr(exc)}")

    _background_executor().submit(_run)


class SwappableBackend:
    """包一层代理：外部长期持有这个对象的引用（比如 YoloDetectionModel.model、
    FClipInferencer.model），对象内部真正的推理后端可以被后台线程原子替换
    （PyTorch -> TensorRT），外部完全不用关心、不用改任何调用代码——属性访问、
    方法调用、直接 __call__() 都透明转发给当前的内部对象。
    """

    def __init__(self, initial: Any):
        object.__setattr__(self, "_current", initial)

    def _swap(self, new_backend: Any) -> None:
        # Python的属性赋值本身是原子的（GIL保证），正在进行中的调用拿着的是
        # 替换前的对象引用，会自然地用旧后端跑完，不会出现一半新一半旧的状态；
        # 下一次调用开始就会读到新对象。
        object.__setattr__(self, "_current", new_backend)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_current"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_current"), name, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return object.__getattribute__(self, "_current")(*args, **kwargs)


def is_tensorrt_enabled() -> bool:
    return os.environ.get("INFERENCE_USE_TENSORRT", "true").strip().lower() not in {"0", "false", "no", "off"}


def _lock_for(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _ensure_cudart_loadable() -> None:
    """pip 安装的 nvidia-cuda-runtime 包里通常只有带版本号的 libcudart.so.N，没有
    无版本号的 libcudart.so 符号链接；TensorRT 内部有些路径会直接 dlopen 无版本号的
    名字，找不到就会在构建/加载 engine 时报错。这里在真正用到 TensorRT 之前，扫一遍
    site-packages 把符号链接补上（如果目录不可写就跳过，改用 LD_LIBRARY_PATH 兜底，
    由 Dockerfile/compose 里设置)。"""
    global _CUDART_FIX_DONE
    if _CUDART_FIX_DONE:
        return
    _CUDART_FIX_DONE = True
    try:
        import nvidia  # noqa: F401
    except ImportError:
        return
    try:
        # nvidia 在装了多个 nvidia-*-cuXX 子包后会变成命名空间包，没有真正的
        # __file__（是None），必须用__path__（命名空间包总有这个）来定位目录。
        nvidia_roots = [Path(p) for p in getattr(nvidia, "__path__", [])]
        if not nvidia_roots and getattr(nvidia, "__file__", None):
            nvidia_roots = [Path(nvidia.__file__).parent]
        for nvidia_root in nvidia_roots:
            for so_path in nvidia_root.glob("*/lib/libcudart.so.*"):
                unversioned = so_path.parent / "libcudart.so"
                if not unversioned.exists():
                    try:
                        unversioned.symlink_to(so_path.name)
                    except OSError:
                        pass
                os.environ["LD_LIBRARY_PATH"] = f"{so_path.parent}:{os.environ.get('LD_LIBRARY_PATH', '')}"
                try:
                    ctypes.CDLL(str(so_path))
                except OSError:
                    pass
    except Exception as exc:  # 这个修复本身绝不能拖垮启动
        print(f"[trt_backend] cudart 符号链接修复失败（忽略，继续尝试TensorRT）: {exc}")


def cache_root() -> Path:
    root = Path(os.environ.get("TRT_ENGINE_CACHE_DIR", "/app/model/engine_cache"))
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        # 容器里没挂到持久卷、当前用户又没权限时，退回权重文件旁边的隐藏目录，
        # 至少同一次容器生命周期内不用重复构建。
        root = Path.cwd() / ".trt_engine_cache"
        root.mkdir(parents=True, exist_ok=True)
    return root


def _gpu_tag() -> str:
    try:
        import torch

        if not torch.cuda.is_available():
            return "cpu"
        major, minor = torch.cuda.get_device_capability(0)
        name = torch.cuda.get_device_name(0).replace(" ", "_")
        return f"{name}_sm{major}{minor}"
    except Exception:
        return "unknown_gpu"


def _trt_version_tag() -> str:
    try:
        import tensorrt as trt

        return trt.__version__
    except Exception:
        return "no_trt"


def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}_{int(stat.st_mtime)}"


def engine_cache_path(name: str, source_path: Path, precision: str = "fp16", extra: str = "") -> Path:
    """给定一个逻辑名字(比如"weldROI4")和源权重文件，算出这次环境下应该用的engine路径。
    路径本身就编码了 GPU型号+TensorRT版本+源文件指纹，环境或权重一变，key就变，
    自然不会误用不匹配的旧缓存。"""
    tag = f"{_gpu_tag()}__trt{_trt_version_tag()}__{precision}__{_file_fingerprint(source_path)}__{extra}"
    digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()[:16]
    return cache_root() / f"{name}__{digest}.engine"


def load_yolo_model(pt_path: str, imgsz: int = 640, half: bool = True):
    """加载YOLO模型，优先用TensorRT engine（懒构建+缓存+后台异步升级），任何一步
    失败都安全回退到原始 .pt 权重。

    - engine 缓存已命中：直接返回 engine 版本，和原来一样快。
    - 没命中：立即返回 PyTorch 版本（包一层可热替换代理），不阻塞调用方；真正的
      engine 构建丢进后台队列，建好后原地把代理换成 engine 版本。
    """
    from ultralytics import YOLO

    pt_path_obj = Path(pt_path)
    if not is_tensorrt_enabled() or not pt_path_obj.exists():
        return YOLO(str(pt_path))

    cached = _lookup_yolo_engine_cache(pt_path_obj, imgsz, half)
    if cached is not None:
        loaded = _load_yolo_engine_file(cached, pt_path_obj)
        if loaded is not None:
            return loaded
        return YOLO(str(pt_path))

    pt_model = YOLO(str(pt_path))
    proxy = SwappableBackend(pt_model)

    def _background_build() -> None:
        engine_path = _build_yolo_engine_now(pt_path_obj, imgsz, half)
        if engine_path is None:
            return
        loaded = _load_yolo_engine_file(Path(engine_path), pt_path_obj)
        if loaded is not None:
            proxy._swap(loaded)
            print(f"[trt_backend] {pt_path_obj.stem} 后台构建完成，已热替换为 TensorRT engine 推理")

    _submit_background(_background_build)
    return proxy


def _lookup_yolo_engine_cache(pt_path: Path, imgsz: int, half: bool) -> Optional[Path]:
    """只查缓存是否已经存在，不触发构建。"""
    name = pt_path.stem
    cached = engine_cache_path(name, pt_path, precision="fp16" if half else "fp32", extra=f"imgsz{imgsz}")
    return cached if cached.exists() else None


def _load_yolo_engine_file(cached: Path, pt_path: Path):
    from ultralytics import YOLO

    task_file = cached.with_suffix(".task.txt")
    try:
        if task_file.exists():
            task = task_file.read_text(encoding="utf-8").strip()
            return YOLO(str(cached), task=task)
        return YOLO(str(cached))
    except Exception as exc:
        print(f"[trt_backend] 加载 {pt_path} 的TensorRT engine失败，回退到PyTorch权重: {str(exc) or repr(exc)}")
        return None


def _build_yolo_engine_now(pt_path: Path, imgsz: int, half: bool) -> Optional[str]:
    """用 ultralytics 自带的导出能力实际构建一次 YOLO 的 TensorRT engine（同步、
    耗时，只应该在后台队列的 worker 线程里调用）。返回engine路径字符串；任何失败
    都返回None，调用方应回退到原始.pt。"""
    _ensure_cudart_loadable()

    name = pt_path.stem
    cached = engine_cache_path(name, pt_path, precision="fp16" if half else "fp32", extra=f"imgsz{imgsz}")
    lock = _lock_for(str(cached))
    with lock:
        if cached.exists():
            return str(cached)
        try:
            import tensorrt  # noqa: F401
            from ultralytics import YOLO
        except Exception as exc:
            print(f"[trt_backend] TensorRT/ultralytics 不可用，{name} 继续用PyTorch: {exc}")
            return None

        print(f"[trt_backend] 首次为 {name} 构建 TensorRT engine（缓存到 {cached}）...")
        try:
            # ultralytics 的 export() 默认把 onnx/engine 写在源权重旁边。生产环境里
            # 权重可能来自只读挂载的模型分发卷（/app/model/store 对ai-inference是
            # :ro），直接在那里 export 会报 Read-only file system。这里先把源权重
            # 复制一份到engine缓存目录下的可写暂存区，export这份拷贝即可。
            staging_dir = cache_root() / "_yolo_export_staging"
            staging_dir.mkdir(parents=True, exist_ok=True)
            staged_pt = staging_dir / pt_path.name
            if not staged_pt.exists() or staged_pt.stat().st_mtime < pt_path.stat().st_mtime:
                shutil.copy2(pt_path, staged_pt)

            export_model = YOLO(str(staged_pt))
            task = export_model.task
            with _EXPORT_SERIALIZE_LOCK:
                exported = export_model.export(
                    format="engine", half=half, imgsz=imgsz, device=0, dynamic=False, simplify=True,
                )
            exported_path = Path(exported)
            cached.parent.mkdir(parents=True, exist_ok=True)
            # replace()在跨文件系统/挂载点时会报Invalid cross-device link；staging
            # 目录按设计和cached在同一个卷下不该触发，但shutil.move兜底更稳妥。
            shutil.move(str(exported_path), str(cached))
            cached.with_suffix(".task.txt").write_text(task, encoding="utf-8")
            # 暂存目录里多余的onnx中间产物没必要留着占地方
            for leftover in staging_dir.glob(f"{staged_pt.stem}.*"):
                if leftover != staged_pt:
                    leftover.unlink(missing_ok=True)
            print(f"[trt_backend] {name} engine 构建完成: {cached}")
            return str(cached)
        except Exception as exc:
            print(f"[trt_backend] {name} 构建 TensorRT engine 失败，回退到PyTorch权重: {str(exc) or repr(exc)}")
            return None


def _autocast_fp16_onnx(onnx_path: Path) -> Optional[Path]:
    """用 NVIDIA modelopt 的 AutoCast 做逐算子安全性判断的FP16转换（比整图硬转靠谱，
    尤其是transformer里的残差连接容易在硬转下出现类型不一致）。失败返回None。"""
    try:
        import modelopt.onnx.autocast as autocast
        import onnx
    except Exception as exc:
        print(f"[trt_backend] modelopt AutoCast 不可用，跳过FP16转换: {exc}")
        return None
    try:
        fp16_path = onnx_path.with_name(onnx_path.stem + ".fp16.onnx")
        model_fp16 = autocast.convert_to_mixed_precision(
            str(onnx_path), low_precision_type="fp16", keep_io_types=True,
        )
        onnx.save(model_fp16, str(fp16_path))
        return fp16_path
    except Exception as exc:
        print(f"[trt_backend] AutoCast FP16 转换失败，回退到FP32 engine: {exc}")
        return None


def ensure_engine_async(
    cache_key_name: str,
    source_path: Path,
    export_onnx_fn: Callable[[Path], None],
    on_ready: Callable[[str], None],
    prefer_fp16: bool = True,
    extra_tag: str = "",
) -> Optional[str]:
    """通用（非YOLO）模型的 ONNX -> TensorRT 构建入口：缓存命中直接返回路径（同步，
    和原来一样快）；没命中则返回 None，同时把真正的构建丢进后台队列，构建成功后用
    engine路径调用一次 on_ready(engine_path)——调用方应该在这个回调里把自己持有的
    模型对象原地换成 TensorRT 版本（通常就是一次属性赋值，Python对象赋值本身是
    原子的，不需要额外加锁）。

    调用方在拿到 None 时，应该让当前这次调用先用 PyTorch 权重继续，不要等这个
    函数——这正是避免 model-agent 热切换被TensorRT构建耗时拖慢/超时的关键。
    """
    if not is_tensorrt_enabled():
        return None
    cached = _lookup_generic_engine_cache(cache_key_name, source_path, prefer_fp16, extra_tag)
    if cached is not None:
        return str(cached)

    def _background_build() -> None:
        engine_path = _build_generic_engine_now(
            cache_key_name, source_path, export_onnx_fn, prefer_fp16, extra_tag,
        )
        if engine_path is not None:
            on_ready(engine_path)

    _submit_background(_background_build)
    return None


def _lookup_generic_engine_cache(
    cache_key_name: str, source_path: Path, prefer_fp16: bool = True, extra_tag: str = "",
) -> Optional[Path]:
    """只查缓存是否已经存在，不触发构建。"""
    precision = "fp16" if prefer_fp16 else "fp32"
    cached = engine_cache_path(cache_key_name, source_path, precision=precision, extra=extra_tag)
    return cached if cached.exists() else None


def _build_generic_engine_now(
    cache_key_name: str,
    source_path: Path,
    export_onnx_fn: Callable[[Path], None],
    prefer_fp16: bool = True,
    extra_tag: str = "",
) -> Optional[str]:
    """实际执行一次通用模型的 ONNX -> TensorRT 构建（同步、耗时，只应该在后台队列
    的 worker 线程里调用）。

    export_onnx_fn(onnx_path) 由调用方提供：把当前已经加载好的PyTorch模型/子模块
    导出成 onnx_path 指向的 ONNX 文件。本函数负责后续的FP16转换（失败自动退回FP32）
    和 polygraphy engine 构建、缓存管理。
    """
    _ensure_cudart_loadable()

    precision = "fp16" if prefer_fp16 else "fp32"
    cached = engine_cache_path(cache_key_name, source_path, precision=precision, extra=extra_tag)
    lock = _lock_for(str(cached))
    with lock:
        if cached.exists():
            return str(cached)
        try:
            import onnx  # noqa: F401
            from polygraphy.backend.trt import CreateConfig, EngineFromNetwork, NetworkFromOnnxPath, SaveEngine
        except Exception as exc:
            print(f"[trt_backend] TensorRT/polygraphy 不可用，{cache_key_name} 继续用PyTorch: {exc}")
            return None

        print(f"[trt_backend] 首次为 {cache_key_name} 构建 TensorRT engine（缓存到 {cached}）...")
        onnx_dir = cache_root() / "_onnx_tmp"
        onnx_dir.mkdir(parents=True, exist_ok=True)
        onnx_path = onnx_dir / f"{cache_key_name}.onnx"
        try:
            with _EXPORT_SERIALIZE_LOCK:
                export_onnx_fn(onnx_path)
        except Exception as exc:
            detail = str(exc) or repr(exc)
            print(f"[trt_backend] {cache_key_name} 导出ONNX失败，回退到PyTorch: {detail}")
            return None

        target_onnx = onnx_path
        used_fp16 = False
        if prefer_fp16:
            fp16_onnx = _autocast_fp16_onnx(onnx_path)
            if fp16_onnx is not None:
                target_onnx = fp16_onnx
                used_fp16 = True

        def _build(onnx_file: Path) -> bool:
            try:
                build_engine = SaveEngine(
                    EngineFromNetwork(NetworkFromOnnxPath(str(onnx_file)), config=CreateConfig()),
                    path=str(cached),
                )
                build_engine()
                return True
            except Exception as exc:
                print(f"[trt_backend] {cache_key_name} 用 {onnx_file.name} 构建engine失败: {str(exc) or repr(exc)}")
                return False

        ok = _build(target_onnx)
        if not ok and used_fp16:
            print(f"[trt_backend] {cache_key_name} FP16 engine 构建失败，退回FP32 ONNX重试...")
            ok = _build(onnx_path)
        if not ok:
            return None
        print(f"[trt_backend] {cache_key_name} engine 构建完成: {cached}")
        return str(cached)


def wrap_classifier_with_tensorrt(
    pytorch_model,
    weight_path: Path,
    device: str,
    input_shape: Sequence[int] = (1, 3, 224, 224),
    cache_key_name: Optional[str] = None,
):
    """给一个已经加载好、单输入单输出（tensor in -> logits tensor out）的PyTorch分类器，
    尝试换成TensorRT engine跑推理。缓存命中直接返回engine版本；没命中就先返回
    PyTorch版本（包一层可热替换代理），构建丢后台，建好后原地热替换。任何一步失败
    都继续用PyTorch，调用方完全不用关心是否真的用上了TensorRT。"""
    if not is_tensorrt_enabled():
        return pytorch_model
    weight_path = Path(weight_path)
    name = cache_key_name or weight_path.stem

    def _export(onnx_path: Path) -> None:
        import torch

        dummy = torch.randn(*input_shape, device=device)
        torch.onnx.export(
            pytorch_model, dummy, str(onnx_path),
            input_names=["input"], output_names=["output"],
            opset_version=17, dynamo=False,
        )

    def _load_engine(engine_path: str):
        try:
            return TrtRunnerModule(engine_path, input_name="input", output_names=["output"])
        except Exception as exc:
            print(f"[trt_backend] {name} 加载TensorRT engine失败，继续用PyTorch: {str(exc) or repr(exc)}")
            return None

    proxy = SwappableBackend(pytorch_model)

    def _on_ready(engine_path: str) -> None:
        loaded = _load_engine(engine_path)
        if loaded is not None:
            proxy._swap(loaded)
            print(f"[trt_backend] {name} 后台构建完成，已热替换为 TensorRT engine 推理")

    engine_path = ensure_engine_async(name, weight_path, _export, _on_ready, prefer_fp16=True)
    if engine_path is None:
        # 缓存未命中：已经提交后台构建，这次先用PyTorch（走proxy）。
        return proxy
    loaded = _load_engine(engine_path)
    return loaded if loaded is not None else pytorch_model


class TrtRunnerModule:
    """把一个 TensorRT engine 包装成可以像 nn.Module 一样直接 __call__(tensor) 调用
    的对象，torch.Tensor 输入 / torch.Tensor（或多输出时dict[str, Tensor]）输出，
    这样可以在现有代码里原地替换 `self.model = SomeTorchModel(...)`，调用方无需改动。
    """

    def __init__(self, engine_path: str, input_name: str, output_names: Optional[Sequence[str]] = None):
        import torch
        from polygraphy.backend.trt import EngineFromBytes, TrtRunner

        self._torch = torch
        self.input_name = input_name
        self.output_names = list(output_names) if output_names else None
        self._engine_path = str(engine_path)
        self._call_count = 0
        engine = EngineFromBytes(Path(engine_path).read_bytes())
        self._runner_cm = TrtRunner(engine)
        self._runner = self._runner_cm.__enter__()

    def eval(self):
        return self

    def to(self, *_args, **_kwargs):
        return self

    def __call__(self, tensor):
        torch = self._torch
        device = tensor.device
        self._call_count += 1
        if self._call_count == 1:
            # 第一次真正跑推理时打一行日志，方便现场确认这次请求确实走了
            # TensorRT engine，而不是只在容器启动时加载engine但推理时又没用上。
            print(f"[trt_backend] 首次真实推理命中 TensorRT engine: {self._engine_path}")
        input_np = tensor.detach().cpu().numpy()
        out = self._runner.infer({self.input_name: input_np})
        values = list(out.values())
        if self.output_names is None or len(values) == 1:
            return torch.from_numpy(values[0]).to(device)
        keys = self.output_names if self.output_names else list(out.keys())
        return {k: torch.from_numpy(v).to(device) for k, v in zip(keys, values)}

    def close(self):
        try:
            self._runner_cm.__exit__(None, None, None)
        except Exception:
            pass

    def __del__(self):
        self.close()
