#!/usr/bin/env python3
"""Validate F-Clip with count precision.
Usage:
    single_valid.py [options] <model-config> <ckpt>
    single_valid.py (-h | --help )

Arguments:
   <model-config>                  Path to model yaml config
   <ckpt>                          Path to ckpt

Options:
   -h --help                       Show this screen.
   -d --devices <devices>          Comma seperated GPU devices [default: 0]
   --params <file>                 Params yaml file [default: params.yaml]
   --output_dir <dir>              Output directory for logs/vis [default: logs/valid]
   --vis                           Save visualization results.
   --threshold <t>                 Heatmap threshold [default: 0.4]
   --fig                           Save count error distribution plot.
   --fig-path <path>               Optional output path for the plot.
   --fig-font <path>               Optional TTF/OTF font file for Chinese labels (auto-detect if empty).
"""

import json
import os
from docopt import docopt
import torch

from FClip.config import C, M
from FClip.datasets import collate
from FClip.datasets import LineDataset as WireframeDataset
from FClip.config_loader import load_configs
from FClip.infer_utils import build_infer_model
from FClip.valid_utils import evaluate_count_precision, evaluate_count_statistics


def main():
    args = docopt(__doc__)
    config_file = args["<model-config>"]
    ckpt = args["<ckpt>"]
    params_file = args["--params"]
    load_configs(model_yaml=config_file, params_yaml=params_file, ckpt=ckpt)

    os.environ["CUDA_VISIBLE_DEVICES"] = args["--devices"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    val_loader = torch.utils.data.DataLoader(
        WireframeDataset(C.io.datadir, split="valid", dataset=C.io.dataname),
        batch_size=C.model.eval_batch_size,
        shuffle=False,
        collate_fn=collate,
        num_workers=C.io.num_workers,
        pin_memory=True,
    )

    model = build_infer_model(device)

    out_dir = args["--output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    vis = bool(args["--vis"])
    vis_dir = os.path.join(out_dir, "vis")
    threshold = float(args["--threshold"])

    image_getter = val_loader.dataset._get_im_name
    fig_enabled = bool(args["--fig"])
    if fig_enabled:
        precision, errors = evaluate_count_statistics(
            model=model,
            val_loader=val_loader,
            device=device,
            threshold=threshold,
            vis=vis,
            vis_dir=vis_dir if vis else None,
            image_getter=image_getter if vis else None,
        )
    else:
        precision = evaluate_count_precision(
            model=model,
            val_loader=val_loader,
            device=device,
            threshold=threshold,
            vis=vis,
            vis_dir=vis_dir if vis else None,
            image_getter=image_getter if vis else None,
        )

    with open(os.path.join(out_dir, "precision.txt"), "w") as f:
        f.write(f"{precision:.6f}\n")
    print(f"count precision: {precision:.6f}")

    if fig_enabled:
        total = len(errors)
        def rate(count):
            return count / max(total, 1)

        err0 = sum(1 for e in errors if e == 0)
        err1 = sum(1 for e in errors if e == 1)
        err2 = sum(1 for e in errors if e == 2)
        err3 = sum(1 for e in errors if e == 3)
        err_ge4 = sum(1 for e in errors if e >= 4)
        err_eq5 = sum(1 for e in errors if e == 5)

        detail = {
            "total": total,
            "exact_match_rate": rate(err0),
            "abs_error_eq_1_rate": rate(err1),
            "abs_error_eq_2_rate": rate(err2),
            "abs_error_eq_3_rate": rate(err3),
            "abs_error_ge_4_rate": rate(err_ge4),
            "abs_error_eq_5_rate": rate(err_eq5),
        }

        detail_path = os.path.join(out_dir, "count_error_detail.json")
        with open(detail_path, "w") as f:
            json.dump(detail, f, indent=2)

        labels = [
            "准确匹配率",
            "绝对计数误差=1",
            "绝对计数误差=2",
            "绝对计数误差=3",
            "绝对计数误差≥4",
            "绝对计数误差=5",
        ]
        values = [
            detail["exact_match_rate"],
            detail["abs_error_eq_1_rate"],
            detail["abs_error_eq_2_rate"],
            detail["abs_error_eq_3_rate"],
            detail["abs_error_ge_4_rate"],
            detail["abs_error_eq_5_rate"],
        ]

        fig_path = args["--fig-path"] or os.path.join(out_dir, "count_error_distribution.png")
        font_path = args["--fig-font"]
        try:
            import matplotlib.pyplot as plt
            from matplotlib import font_manager

            def resolve_cjk_font(user_path):
                if user_path:
                    if os.path.exists(user_path):
                        return user_path
                    print(f"font not found: {user_path}, fallback to auto-detect.")
                tokens = [
                    "noto sans cjk",
                    "noto sans sc",
                    "sourcehansans",
                    "source han sans",
                    "wenquanyi",
                    "wqy",
                    "simhei",
                    "simsun",
                    "msyh",
                    "yahei",
                    "pingfang",
                    "heiti",
                    "hiragino",
                    "arialuni",
                ]
                font_paths = []
                for ext in ("ttf", "otf", "ttc"):
                    font_paths.extend(font_manager.findSystemFonts(fontext=ext))
                lower_paths = [(p, p.lower()) for p in font_paths]
                for token in tokens:
                    for path, lower in lower_paths:
                        if token in lower:
                            return path
                return None

            font_path = resolve_cjk_font(font_path)
            font_prop = None
            if font_path:
                font_manager.fontManager.addfont(font_path)
                font_prop = font_manager.FontProperties(fname=font_path)
                try:
                    import matplotlib as mpl

                    mpl.rcParams["font.family"] = "sans-serif"
                    mpl.rcParams["font.sans-serif"] = [font_prop.get_name()]
                    mpl.rcParams["axes.unicode_minus"] = False
                except Exception:
                    pass

            plt.figure(figsize=(8, 4))
            bars = plt.bar(range(len(values)), values, color="#4C78A8")
            if font_prop is not None:
                plt.xticks(range(len(labels)), labels, rotation=30, ha="right", fontproperties=font_prop)
                plt.ylabel("概率", fontproperties=font_prop)
            else:
                plt.xticks(range(len(labels)), labels, rotation=30, ha="right")
                plt.ylabel("概率")
            plt.ylim(0, max(values) * 1.2 if values else 1.0)
            for bar, val in zip(bars, values):
                plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                         f"{val:.2%}", ha="center", va="bottom", fontsize=9)
            plt.tight_layout()
            plt.savefig(fig_path, dpi=200)
            plt.close()
        except ImportError:
            print("matplotlib is not installed; skip saving figure.")

        print("count error breakdown:")
        print(f"  准确匹配率(|Δ|=0):      {detail['exact_match_rate']:.6f}")
        print(f"  绝对计数误差=1:        {detail['abs_error_eq_1_rate']:.6f}")
        print(f"  绝对计数误差=2:        {detail['abs_error_eq_2_rate']:.6f}")
        print(f"  绝对计数误差=3:        {detail['abs_error_eq_3_rate']:.6f}")
        print(f"  绝对计数误差≥4:        {detail['abs_error_ge_4_rate']:.6f}")
        print(f"  绝对计数误差=5:        {detail['abs_error_eq_5_rate']:.6f}")


if __name__ == "__main__":
    main()
