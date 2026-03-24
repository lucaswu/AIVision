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
