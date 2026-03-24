import glob
import os
import cv2

import numpy as np
import torch
from skimage import io
from torch.utils.data import Dataset
from torch.utils.data.dataloader import default_collate

from FClip.config import M, C
from dataset.input_parsing import WireframeHuangKun
from dataset.crop import CropAugmentation
from dataset.resolution import ResizeResolution


def collate(batch):
    return (
        default_collate([b[0] for b in batch]),
        [b[1] for b in batch],
        default_collate([b[2] for b in batch]),
    )


class LineDataset(Dataset):
    def __init__(self, rootdir, split, dataset="shanghaiTech"):
        print("dataset:", dataset)
        self.rootdir = rootdir
        if dataset in ["shanghaiTech", "york", "IQI"]:
            filelist = glob.glob(f"{rootdir}/{split}/*_line.npz")
            if not filelist:
                filelist = glob.glob(f"{rootdir}/{split}/*_label.npz")
            filelist.sort()
        else:
            raise ValueError("no such dataset")

        print(f"n{split}:", len(filelist))
        self.dataset = dataset
        self.split = split
        self.filelist = filelist

    def __len__(self):
        return len(self.filelist)

    def _get_im_name(self, idx):
        if self.dataset in ["shanghaiTech", "york", "IQI"]:
            f = self.filelist[idx]
            if f.endswith("_line.npz"):
                iname = f.replace("_line.npz", ".png")
            else:
                iname = f.replace("_label.npz", ".png")
        else:
            raise ValueError("no such name!")
        return iname

    def __getitem__(self, idx):
        iname = self._get_im_name(idx)
        image_ = io.imread(iname).astype(float)
        if image_.ndim == 2:
            image_ = image_[:, :, None]
        elif image_.ndim == 3:
            if image_.shape[2] > 1:
                r = image_[:, :, 0]
                g = image_[:, :, 1]
                b = image_[:, :, 2]
                gray = 0.299 * r + 0.587 * g + 0.114 * b
                image_ = gray[:, :, None]
            else:
                image_ = image_[:, :, :1]
        else:
            raise ValueError(f"Unexpected image shape: {image_.shape}")

        target = {}
        if M.stage1 == "fclip":

            # step 1 load npz
            fpath = self.filelist[idx]
            if fpath.endswith("_label.npz"):
                line_path = fpath.replace("_label.npz", "_line.npz")
                label_path = fpath
            else:
                line_path = fpath
                label_path = fpath

            lcmap, lcoff, lleng, angle = WireframeHuangKun.fclip_parsing(
                line_path,
                M.ang_type
            )
            is_1d = lcmap.ndim == 2 and lcmap.shape[0] == 1

            lpos = None
            with np.load(label_path) as npz:
                if "lpos" in npz:
                    lpos = npz["lpos"][:, :, :2]
            count = None
            with np.load(line_path) as npz:
                if "count" in npz:
                    count = int(npz["count"])
            if lpos is None:
                alt_label = line_path.replace("_line.npz", "_label.npz")
                if os.path.exists(alt_label):
                    with np.load(alt_label) as npz:
                        if "lpos" in npz:
                            lpos = npz["lpos"][:, :, :2]
            if lpos is None:
                raise ValueError(f"Missing lpos in {label_path} (or {alt_label}).")

            meta = {
                "lpre": torch.from_numpy(lpos[:, :, :2]),
                "lpre_label": torch.ones(len(lpos)),
            }

            # step 2 crop augment
            if (self.split == "train" and M.crop and not is_1d and lpos is not None and len(lpos) > 0):
                s = np.random.choice(np.arange(0.9, M.crop_factor, 0.1))
                image_t, lcmap, lcoff, lleng, angle, cropped_lines, cropped_region = (
                    CropAugmentation.random_crop_augmentation(image_, lpos, s)
                )
                image_ = image_t
                lpos = cropped_lines

            # step 3 resize
            if M.resolution < 128:
                if is_1d:
                    input_h = getattr(M, "input_resolution_h", M.resolution * 4)
                    input_w = getattr(M, "input_resolution_w", M.resolution * 4)
                    target_size = (input_w, input_h)
                    if image_.shape[0] != target_size[1] or image_.shape[1] != target_size[0]:
                        image_ = cv2.resize(image_, target_size)
                        if image_.ndim == 2:
                            image_ = image_[:, :, None]
                else:
                    image_, lcmap, lcoff, lleng, angle = ResizeResolution.resize(
                        lpos=lpos, image=image_, resolu=M.resolution)

            target["lcmap"] = torch.from_numpy(lcmap).float()
            target["lcoff"] = torch.from_numpy(lcoff).float()
            target["lleng"] = torch.from_numpy(lleng).float()
            target["angle"] = torch.from_numpy(angle).float()
            if count is None:
                count = 0
            target["count"] = torch.tensor(count).long()

        else:
            raise NotImplementedError

        if image_.ndim == 2:
            image_ = image_[:, :, None]
        elif image_.ndim == 3 and image_.shape[2] != 1:
            image_ = image_[:, :, :1]
        image = (image_ - M.image.mean) / M.image.stddev
        image = np.rollaxis(image, 2).copy()

        return torch.from_numpy(image).float(), meta, target
