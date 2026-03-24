import math
import torch
import numpy as np
import torch.nn.functional as F

from FClip.nms import non_maximum_suppression, structure_nms


class PointParsing():

    @staticmethod
    def jheatmap_torch(jmap, joff, delta=0.8, K=1000, kernel=3, joff_type="raw", resolution=128):
        h, w = jmap.shape
        lcmap = non_maximum_suppression(jmap[None, ...], delta, kernel).reshape(-1)
        score, index = torch.topk(lcmap, k=int(K))

        if joff is not None:
            lcoff = joff.reshape(2, -1)
            if joff_type == "raw":
                y = (index // w).float() + lcoff[0][index] + 0.5
                x = (index % w).float() + lcoff[1][index] + 0.5
            elif joff_type == "gaussian":
                y = (index // w).float() + lcoff[0][index]
                x = (index % w).float() + lcoff[1][index]
            else:
                raise NotImplementedError
        else:
            y = (index // w).float()
            x = (index % w).float()

        yx = torch.cat([y[..., None], x[..., None]], dim=-1).clamp(0, resolution - 1e-6)

        return yx, score, index

    @staticmethod
    def jheatmap_numpy(jmap, joff, delta=0.8, K=1000, kernel=3, resolution=128):

        jmap = torch.from_numpy(jmap)
        if joff is not None:
            joff = torch.from_numpy(joff)
        xy, score, index = PointParsing.jheatmap_torch(jmap, joff, delta, K, kernel, resolution=resolution)
        v = torch.cat([xy, score[:, None]], 1)
        return v.numpy()


class OneStageLineParsing():
    # @staticmethod
    # def get_resolution():
    #     return C.model.resolution

    @staticmethod
    def fclip_numpy(lcmap, lcoff, lleng, angle, delta=0.8, nlines=1000, ang_type="radian", kernel=3, resolution=128):
        lcmap = torch.from_numpy(lcmap)
        lcoff = torch.from_numpy(lcoff)
        lleng = torch.from_numpy(lleng)
        angle = torch.from_numpy(angle)

        lines, scores = OneStageLineParsing.fclip_torch(lcmap, lcoff, lleng, angle, delta, nlines, ang_type, kernel, resolution=resolution)

        return lines.numpy(), scores.numpy()

    @staticmethod
    def fclip_torch(lcmap, lcoff, lleng, angle, delta=0.8, nlines=1000, ang_type="radian", kernel=3, resolution=128):

        xy, score, index = PointParsing.jheatmap_torch(lcmap, lcoff, delta, nlines, kernel, resolution=resolution)
        lines = OneStageLineParsing.fclip_merge(xy, index, lleng, angle, ang_type, resolution=resolution)

        return lines, score

    @staticmethod
    def fclip_merge(xy, xy_idx, length_regress, angle_regress, ang_type="radian", resolution=128):
        """
        :param xy: (K, 2)
        :param xy_idx: (K,)
        :param length_regress: (H, W)
        :param angle_regress:  (H, W)
        :param ang_type
        :param resolution
        :return:
        """
        # resolution = OneStageLineParsing.get_resolution()
        xy_idx = xy_idx.reshape(-1)
        lleng_regress = length_regress.reshape(-1)[xy_idx]  # (K,)
        angle_regress = angle_regress.reshape(-1)[xy_idx]   # (K,)

        lengths = lleng_regress * (resolution / 2)
        if ang_type == "cosine":
            angles = angle_regress * 2 - 1
        elif ang_type == "radian":
            angles = torch.cos(angle_regress * np.pi)
        else:
            raise NotImplementedError
        angles1 = -torch.sqrt(1-angles**2)
        direction = torch.cat([angles1[:, None], angles[:, None]], 1)  # (K, 2)
        v1 = (xy + direction * lengths[:, None]).clamp(0, resolution)
        v2 = (xy - direction * lengths[:, None]).clamp(0, resolution)

        return torch.cat([v1[:, None], v2[:, None]], 1)

    @staticmethod
    def _nms_1d(scores, delta=0.0, kernel=3):
        scores = scores.reshape(1, 1, -1)
        ap = F.max_pool1d(scores, kernel, stride=1, padding=kernel // 2)
        mask = (scores == ap).float().clamp(min=0.0)
        mask_n = (~mask.bool()).float() * delta
        return (scores * mask + scores * mask_n).reshape(-1)

    @staticmethod
    def _line_endpoints(x0, y0, dx, dy, width, height):
        eps = 1e-6
        points = []
        if abs(dx) > eps:
            t = (0.0 - x0) / dx
            y = y0 + t * dy
            if 0.0 <= y <= height - 1:
                points.append((0.0, y))
            t = ((width - 1) - x0) / dx
            y = y0 + t * dy
            if 0.0 <= y <= height - 1:
                points.append((width - 1.0, y))
        if abs(dy) > eps:
            t = (0.0 - y0) / dy
            x = x0 + t * dx
            if 0.0 <= x <= width - 1:
                points.append((x, 0.0))
            t = ((height - 1) - y0) / dy
            x = x0 + t * dx
            if 0.0 <= x <= width - 1:
                points.append((x, height - 1.0))
        if len(points) < 2:
            if abs(dx) <= eps:
                return (x0, 0.0), (x0, height - 1.0)
            if abs(dy) <= eps:
                return (0.0, y0), (width - 1.0, y0)
            if points:
                return points[0], points[0]
            return (x0, y0), (x0, y0)
        if len(points) > 2:
            max_d = -1.0
            p0 = p1 = points[0]
            for i in range(len(points)):
                for j in range(i + 1, len(points)):
                    dxp = points[i][0] - points[j][0]
                    dyp = points[i][1] - points[j][1]
                    d = dxp * dxp + dyp * dyp
                    if d > max_d:
                        max_d = d
                        p0, p1 = points[i], points[j]
            return p0, p1
        return points[0], points[1]

    @staticmethod
    def fclip_1d_torch(lcmap, lcoff, angle, delta=0.8, nlines=1000, ang_type="radian", kernel=3, resolution=64, count=None):
        scores = lcmap.reshape(-1)
        scores = OneStageLineParsing._nms_1d(scores, delta=delta, kernel=kernel)
        device = lcmap.device
        max_lines = int(nlines) if nlines is not None else scores.numel()
        if count is not None:
            k = min(int(count), max_lines, scores.numel())
            if k <= 0:
                return torch.zeros((max_lines, 2, 2), device=device), torch.zeros((max_lines,), device=device)
            vals, idx = torch.topk(scores, k=k)
        else:
            k = min(max_lines, scores.numel())
            vals, idx = torch.topk(scores, k=k)
            keep = vals > delta
            vals = vals[keep]
            idx = idx[keep]
            if idx.numel() == 0:
                return torch.zeros((max_lines, 2, 2), device=device), torch.zeros((max_lines,), device=device)

        if lcoff is not None:
            lcoff_x = lcoff.reshape(-1)
            x = idx.float() + lcoff_x[idx] + 0.5
        else:
            x = idx.float() + 0.5
        x = x.clamp(0, resolution - 1e-4)

        if angle is None:
            ang = torch.zeros_like(x)
        else:
            ang = angle.reshape(-1)[idx]

        lines = torch.zeros((max_lines, 2, 2), device=device)
        scores_out = torch.zeros((max_lines,), device=device)
        y_center = (resolution - 1) / 2.0
        width = float(resolution)
        height = float(resolution)
        for i in range(x.shape[0]):
            xi = float(x[i].item())
            ai = float(ang[i].item())
            if ang_type == "cosine":
                cos_v = ai * 2.0 - 1.0
            elif ang_type == "radian":
                cos_v = math.cos(ai * math.pi)
            else:
                raise NotImplementedError
            cos_v = max(min(cos_v, 1.0 - 1e-6), -1.0 + 1e-6)
            sin_v = -math.sqrt(1.0 - cos_v * cos_v)
            (x0, y0), (x1, y1) = OneStageLineParsing._line_endpoints(
                xi, y_center, cos_v, sin_v, width, height
            )
            lines[i, 0, 0] = y0
            lines[i, 0, 1] = x0
            lines[i, 1, 0] = y1
            lines[i, 1, 1] = x1
            scores_out[i] = vals[i]

        return lines, scores_out


def line_parsing_from_npz(
        npz_name, ang_type="radian",
        delta=0.8, nlines=1000, kernel=3,
        s_nms=0, resolution=128
):
    # -------line parsing----
    with np.load(npz_name) as fpred:
        lcmap = fpred["lcmap"]
        lcoff = fpred["lcoff"]
        lleng = fpred["lleng"]
        angle = fpred["angle"]
        if lcmap.ndim == 2 and lcmap.shape[0] == 1:
            count = None
            if "count" in fpred:
                count = int(np.argmax(fpred["count"]))
            line_t, score_t = OneStageLineParsing.fclip_1d_torch(
                torch.from_numpy(lcmap),
                torch.from_numpy(lcoff),
                torch.from_numpy(angle),
                delta=delta,
                nlines=nlines,
                ang_type=ang_type,
                kernel=kernel,
                resolution=resolution,
                count=count,
            )
            line, score = line_t.numpy(), score_t.numpy()
        else:
            line, score = OneStageLineParsing.fclip_numpy(
                lcmap, lcoff, lleng, angle, delta, nlines, ang_type, kernel, resolution=resolution
            )

    # ---------step 2 remove line by structure nms ----
    if s_nms > 0:
        line, score = structure_nms(line, score, s_nms)


    return line, score
