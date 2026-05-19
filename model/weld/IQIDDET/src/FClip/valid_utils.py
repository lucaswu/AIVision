import os
import cv2 as cv
import torch

from FClip.config import M
from FClip.infer_utils import (
    get_count_pred,
    parse_lines_1d,
    scale_lines,
    draw_lines,
    draw_count_pair,
)


def evaluate_count_statistics(
    model,
    val_loader,
    device,
    threshold=0.4,
    vis=False,
    vis_dir=None,
    image_getter=None,
):
    model.eval()
    correct = 0
    total = 0
    errors = []

    if vis:
        if vis_dir is None or image_getter is None:
            raise ValueError("vis=True requires vis_dir and image_getter.")
        os.makedirs(vis_dir, exist_ok=True)
        vis_right = os.path.join(vis_dir, "right")
        vis_error = os.path.join(vis_dir, "error")
        os.makedirs(vis_right, exist_ok=True)
        os.makedirs(vis_error, exist_ok=True)

    with torch.no_grad():
        for batch_idx, (image, meta, target) in enumerate(val_loader):
            input_dict = {"image": image.to(device)}
            outputs = model(input_dict, isTest=True)
            heatmaps = outputs["heatmaps"]

            pred = get_count_pred(heatmaps)
            if pred is None:
                raise ValueError("Model outputs missing count head.")
            gt = target["count"].to(pred.device)

            diff = (pred - gt).abs()
            errors.extend(diff.detach().cpu().tolist())
            correct += (diff == 0).sum().item()
            total += gt.numel()

            if vis:
                batch_size = image.shape[0]
                for i in range(batch_size):
                    index = batch_idx * val_loader.batch_size + i
                    img_path = image_getter(index)
                    img = cv.imread(img_path)
                    if img is None:
                        continue

                    lcmap = heatmaps["lcmap"][i]
                    lcoff = heatmaps["lcoff"][i]
                    angle = heatmaps["angle"][i]
                    lines, scores = parse_lines_1d(
                        lcmap=lcmap,
                        lcoff=lcoff,
                        angle=angle,
                        threshold=threshold,
                        nlines=M.nlines,
                        resolution=M.resolution,
                        ang_type=M.ang_type,
                        count_pred=int(pred[i].item()),
                    )
                    lines = scale_lines(lines, M.resolution, img.shape)
                    lines_np = lines.cpu().numpy()
                    draw_lines(img, lines_np)
                    pred_i = int(pred[i].item())
                    gt_i = int(gt[i].item())
                    draw_count_pair(img, pred_i, gt_i)
                    out_dir = vis_right if pred_i == gt_i else vis_error
                    cv.imwrite(os.path.join(out_dir, f"{index:06}.png"), img)

    precision = correct / max(total, 1)
    return precision, errors


def evaluate_count_precision(
    model,
    val_loader,
    device,
    threshold=0.4,
    vis=False,
    vis_dir=None,
    image_getter=None,
):
    precision, _errors = evaluate_count_statistics(
        model=model,
        val_loader=val_loader,
        device=device,
        threshold=threshold,
        vis=vis,
        vis_dir=vis_dir,
        image_getter=image_getter,
    )
    return precision
