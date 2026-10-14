"""输入收集：把用户选择的文件/目录展开为图像列表，并保留相对路径用于输出结构。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

from .paths import SUPPORTED_IMAGE_EXTS


def collect_inputs(selected: Iterable[Path], recursive: bool = True) -> List[Tuple[Path, Path]]:
    """返回 [(绝对路径, 相对路径)]，按相对路径排序、去重。

    - 选择目录：相对路径相对于该目录；
    - 选择单个文件：相对路径就是文件名。
    """
    seen = set()
    items: List[Tuple[Path, Path]] = []

    def add(path: Path, rel: Path) -> None:
        key = path.resolve()
        if key in seen:
            return
        seen.add(key)
        items.append((path, rel))

    for entry in selected:
        entry = Path(entry)
        if entry.is_dir():
            walker = entry.rglob("*") if recursive else entry.glob("*")
            for p in walker:
                if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS:
                    add(p, p.relative_to(entry))
        elif entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_EXTS:
            add(entry, Path(entry.name))

    items.sort(key=lambda it: str(it[1]).lower())
    return items
