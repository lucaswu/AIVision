import cv2 as cv
import numpy as np
import torch

from FClip.config import C, M
from FClip.config_loader import load_configs
from FClip.models import MultitaskHead, hr
from FClip.models.stage_1 import FClip
from FClip.line_parsing import OneStageLineParsing


def load_config_from_yaml(config_file, params_yaml="params.yaml", ckpt=None):
    load_configs(model_yaml=config_file, params_yaml=params_yaml, ckpt=ckpt)
    return M


def build_infer_model(device):
    if M.backbone == "hrnet":
        model = hr(
            head=lambda c_in, c_out: MultitaskHead(c_in, c_out),
            num_classes=sum(sum(MultitaskHead._get_head_size(), [])),
        )
    else:
        raise NotImplementedError("Only hrnet backbone is supported in this refactor.")

    model = FClip(model)
    model.to(device)

    if C.io.model_initialize_file:
        checkpoint = torch.load(C.io.model_initialize_file, map_location=device)
        state_dict = checkpoint.get("model_state_dict", checkpoint)
        if any(k.startswith("module.") for k in state_dict.keys()):
            state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
        model.load_state_dict(state_dict)
        del checkpoint

    model.eval()

    if C.io.model_initialize_file:
        model = _maybe_wrap_fclip_with_tensorrt(model, C.io.model_initialize_file, device)
    return model


class _FClipBackboneOnly(torch.nn.Module):
    """test_forward() 里"纯张量计算"的那部分：backbone前向 + 头部切片/激活，
    不含逐样本、按.item()做同步的线段解析循环（那部分本来就是Python侧后处理，
    保持不变，只是喂给它的heatmap来源换成TensorRT）。"""

    def __init__(self, fclip_model):
        super().__init__()
        self.backbone = fclip_model.backbone
        self.head_off = fclip_model.head_off
        self.M_dic = fclip_model.M_dic
        self.head_names = ["lcmap", "lcoff", "lleng", "angle"]
        if "count" in self.M_dic.get("head", {}):
            self.head_names.append("count")

    def _pool_height(self, output):
        import torch.nn.functional as F

        if self.M_dic.get("heatmap_1d", False):
            target_w = self.M_dic.get("resolution", output.shape[-1])
            return F.adaptive_avg_pool2d(output, (1, target_w))
        return output

    def forward(self, image):
        outputs, _feature, _t = self.backbone(image)
        output = self._pool_height(outputs[0])
        lcmap = output[:, 0:self.head_off[0]].softmax(1)[:, 1]
        lcoff = output[:, self.head_off[0]:self.head_off[1]].sigmoid() - 0.5
        lleng = output[:, self.head_off[1]:self.head_off[2]].sigmoid()
        angle = output[:, self.head_off[2]:self.head_off[3]].sigmoid()
        result = [lcmap, lcoff, lleng, angle]
        if "count" in self.M_dic.get("head", {}):
            order = self.M_dic["head"]["order"]
            offidx = order.index("count")
            s = 0 if offidx == 0 else self.head_off[offidx - 1]
            e = self.head_off[offidx]
            count = output[:, s:e].mean(dim=(2, 3)).softmax(1)
            result.append(count)
        return tuple(result)


class _FClipTensorRTAdapter:
    """把 backbone+head 的TensorRT engine包成和原始 FClip.forward(...,isTest=True)
    一样的调用形态，这样 infer_heatmaps() 完全不用改。"""

    def __init__(self, trt_module, head_names):
        self._trt = trt_module
        self._head_names = head_names

    def __call__(self, input_dict, isTest=True):
        image = input_dict["image"]
        outputs = self._trt(image)
        if isinstance(outputs, dict):
            heatmap = {name: outputs[name] for name in self._head_names if name in outputs}
        else:
            heatmap = {self._head_names[0]: outputs}
        return {"heatmaps": heatmap, "extra_info": {}}

    def eval(self):
        return self


def _maybe_wrap_fclip_with_tensorrt(model, ckpt_path, device):
    from pathlib import Path

    from utils.trt_backend import TrtRunnerModule, build_generic_engine_if_needed, is_tensorrt_enabled

    if not is_tensorrt_enabled():
        return model

    backbone_only = _FClipBackboneOnly(model).to(device).eval()
    head_names = backbone_only.head_names
    input_h = int(getattr(M, "input_resolution_h", 256))
    input_w = int(getattr(M, "input_resolution_w", 256))

    def _export(onnx_path):
        dummy = torch.randn(1, 1, input_h, input_w, device=device)
        torch.onnx.export(
            backbone_only, dummy, str(onnx_path),
            input_names=["image"], output_names=head_names,
            opset_version=17, dynamo=False,
        )

    engine_path = build_generic_engine_if_needed(
        "fclip_backbone", Path(ckpt_path), _export, prefer_fp16=True,
    )
    if engine_path is None:
        return model
    try:
        trt_module = TrtRunnerModule(engine_path, input_name="image", output_names=head_names)
        print("[FClip] 已切换到 TensorRT engine 推理")
        return _FClipTensorRTAdapter(trt_module, head_names)
    except Exception as exc:
        print(f"[FClip] 加载TensorRT engine失败，回退到PyTorch: {exc}")
        return model


def preprocess_gray_image(img, input_resolution, mean, std, device):
    if img.ndim == 3:
        img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    inp = cv.resize(img, input_resolution)
    inp = (inp.astype(np.float32) - mean) / std
    tensor = torch.from_numpy(inp[None, ...]).float().unsqueeze(0).to(device=device)
    return tensor


def infer_heatmaps(model, image_tensor):
    with torch.no_grad():
        outputs = model({"image": image_tensor}, isTest=True)
    return outputs["heatmaps"]


def get_count_pred(heatmaps):
    if "count" not in heatmaps:
        return None
    return heatmaps["count"].argmax(1)


def parse_lines_1d(lcmap, lcoff, angle, threshold, nlines, resolution, ang_type, count_pred=None):
    lines, scores = OneStageLineParsing.fclip_1d_torch(
        lcmap=lcmap,
        lcoff=lcoff,
        angle=angle,
        delta=threshold,
        nlines=nlines,
        ang_type=ang_type,
        kernel=3,
        resolution=resolution,
        count=count_pred,
    )
    if scores.numel() > 0:
        lines = lines[scores > 0]
        scores = scores[scores > 0]
    return lines, scores


def scale_lines(lines, resolution, out_shape):
    if lines.numel() == 0:
        return lines
    h, w = out_shape[:2]
    lines[:, :, 0] = lines[:, :, 0] * h / resolution
    lines[:, :, 1] = lines[:, :, 1] * w / resolution
    return lines


def draw_lines(image, lines, color=(0, 0, 255), thickness=2):
    out = image
    for i in range(lines.shape[0]):
        start = (int(lines[i][0][1]), int(lines[i][0][0]))
        end = (int(lines[i][1][1]), int(lines[i][1][0]))
        cv.line(out, start, end, color, thickness, lineType=16)
    return out


def draw_count(image, count_pred, color=(0, 255, 255), label="count"):
    if count_pred is None:
        return image
    text = f"{label}: {int(count_pred)}"
    font = cv.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    text_size, _ = cv.getTextSize(text, font, font_scale, thickness)
    x = max(image.shape[1] - text_size[0] - 10, 0)
    y = max(image.shape[0] - 10, text_size[1] + 2)
    cv.putText(image, text, (x, y), font, font_scale, color, thickness, lineType=cv.LINE_AA)
    return image


def draw_count_pair(image, pred, gt, color_pred=(0, 255, 255), color_gt=(255, 255, 0)):
    if pred is None and gt is None:
        return image
    text_pred = f"pred: {int(pred)}" if pred is not None else "pred: N/A"
    text_gt = f"gt: {int(gt)}" if gt is not None else "gt: N/A"

    font = cv.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    size_pred, _ = cv.getTextSize(text_pred, font, font_scale, thickness)
    size_gt, _ = cv.getTextSize(text_gt, font, font_scale, thickness)
    max_w = max(size_pred[0], size_gt[0])
    x = max(image.shape[1] - max_w - 10, 0)
    y_pred = max(image.shape[0] - 10, size_pred[1] + 2)
    y_gt = max(y_pred - size_pred[1] - 8, size_gt[1] + 2)

    cv.putText(image, text_gt, (x, y_gt), font, font_scale, color_gt, thickness, lineType=cv.LINE_AA)
    cv.putText(image, text_pred, (x, y_pred), font, font_scale, color_pred, thickness, lineType=cv.LINE_AA)
    return image
