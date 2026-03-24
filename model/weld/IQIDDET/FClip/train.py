#!/usr/bin/env python3
"""Train L-CNN
Usage:
    train.py [options] <model-config>
    train.py (-h | --help )

Arguments:
   <model-config>                  Path to model yaml config

Options:
   -h --help                       Show this screen.
   -d --devices <devices>          Comma seperated GPU devices [default: 0]
   -i --identifier <identifier>    Folder identifier [default: default-lr]
   --params <file>                 Params yaml file [default: params.yaml]
   --datadir <dir>                 Override dataset dir.
   --logdir <dir>                  Override logdir root.
   --run_name <name>               Fixed output directory name under logdir.
   --batch_size <n>                Override train batch size.
   --eval_batch_size <n>           Override eval batch size.
   --lr <lr>                       Override learning rate.
   --max_epoch <n>                 Override max epochs.
   --metrics_path <path>           Override metrics.json output path. [default: metrics/metrics.json]
"""

import os
import glob
import pprint
import random
import shutil
import os.path as osp
import datetime

import numpy as np
import torch
from docopt import docopt

import FClip
from FClip.config import C, M
from FClip.config_loader import load_configs
from FClip.datasets import collate
from FClip.datasets import LineDataset as WireframeDataset

from FClip.models.stage_1 import FClip
from FClip.models import MultitaskHead, hr
from FClip.lr_schedulers import init_lr_scheduler
from FClip.trainer import Trainer


def get_outdir(identifier, run_name=None):
    # load config
    if run_name:
        name = run_name
    else:
        name = str(datetime.datetime.now().strftime("%y%m%d-%H%M%S"))
        name += "-%s" % identifier
    outdir = osp.join(osp.expanduser(C.io.logdir), name)
    if not osp.exists(outdir):
        os.makedirs(outdir)
    C.io.resume_from = outdir
    C.to_yaml(osp.join(outdir, "config.yaml"))
    return outdir


def build_model():
    if M.backbone == "hrnet":
        model = hr(
            head=lambda c_in, c_out: MultitaskHead(c_in, c_out),
            num_classes=sum(sum(MultitaskHead._get_head_size(), [])),
        )
    else:
        raise NotImplementedError("Only hrnet backbone is supported in this refactor.")

    model = FClip(model).cuda()

    # model = model.cuda()
    # model = DataParallel(model).cuda()

    if C.io.model_initialize_file:
        checkpoint = torch.load(C.io.model_initialize_file)
        model.load_state_dict(checkpoint["model_state_dict"])
        del checkpoint
        print('=> loading model from {}'.format(C.io.model_initialize_file))

    print("Finished constructing model!")
    return model


def main():
    args = docopt(__doc__)
    config_file = args["<model-config>"]
    params_file = args["--params"]
    load_configs(model_yaml=config_file, params_yaml=params_file)
    if args["--datadir"]:
        C.io.datadir = args["--datadir"]
    if args["--logdir"]:
        C.io.logdir = args["--logdir"]
    if args["--run_name"]:
        C.io.run_name = args["--run_name"]
    if args["--batch_size"]:
        C.model.batch_size = int(args["--batch_size"])
    if args["--eval_batch_size"]:
        C.model.eval_batch_size = int(args["--eval_batch_size"])
    if args["--lr"]:
        C.optim.lr = float(args["--lr"])
    if args["--max_epoch"]:
        C.optim.max_epoch = int(args["--max_epoch"])
    metrics_path = args["--metrics_path"] or "metrics/metrics.json"
    metrics_dir = osp.dirname(metrics_path)
    if metrics_dir:
        os.makedirs(metrics_dir, exist_ok=True)
    M.update(C.model)
    pprint.pprint(C, indent=4)
    resume_from = C.io.resume_from

    # WARNING: L-CNN is still not deterministic
    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)

    device_name = "cpu"
    os.environ["CUDA_VISIBLE_DEVICES"] = args["--devices"]
    if torch.cuda.is_available():
        device_name = "cuda"
        torch.backends.cudnn.deterministic = True
        torch.cuda.manual_seed(0)
        print("Let's use", torch.cuda.device_count(), "GPU(s)!")
    else:
        print("CUDA is not available")
    device = torch.device(device_name)

    # 1. dataset
    datadir = C.io.datadir
    kwargs = {
        # "batch_size": M.batch_size,
        "collate_fn": collate,
        "num_workers": C.io.num_workers,
        "pin_memory": True,
    }
    dataname = C.io.dataname
    train_loader = torch.utils.data.DataLoader(
        WireframeDataset(datadir, split="train", dataset=dataname), batch_size=M.batch_size, shuffle=True, drop_last=True, **kwargs
    )
    val_loader = torch.utils.data.DataLoader(
        WireframeDataset(datadir, split="valid", dataset=dataname), batch_size=M.eval_batch_size, **kwargs
    )
    epoch_size = len(train_loader)

    # 2. model
    model = build_model()

    # 3. optimizer
    if C.optim.name == "Adam":
        optim = torch.optim.Adam(
            model.parameters(),
            lr=C.optim.lr,
            weight_decay=C.optim.weight_decay,
            amsgrad=C.optim.amsgrad,
        )
    else:
        raise NotImplementedError

    run_name = args["--run_name"] or getattr(C.io, "run_name", None)
    outdir = get_outdir(args["--identifier"], run_name=run_name)
    print("outdir:", outdir)
    if M.backbone in ["hrnet"]:
        hr_cfg = getattr(M, "hrnet_config", "")
        if hr_cfg and osp.isfile(hr_cfg):
            shutil.copy(hr_cfg, osp.join(outdir, osp.basename(hr_cfg)))

    iteration = 0
    epoch = 0
    best_mean_loss = 1e1000
    best_epoch = -1
    best_precision = 0.0
    if resume_from:
        ckpt_pth = osp.join(resume_from, "checkpoint_lastest.pth.tar")
        checkpoint = torch.load(ckpt_pth)
        iteration = checkpoint["iteration"]
        epoch = iteration // epoch_size
        best_mean_loss = checkpoint["best_mean_loss"]
        best_epoch = checkpoint.get("best_epoch", -1)
        best_precision = checkpoint.get("best_precision", 0.0)
        print(f"loading {epoch}-th ckpt: {ckpt_pth}")

        model.load_state_dict(checkpoint["model_state_dict"])
        optim.load_state_dict(checkpoint["optim_state_dict"])

        lr_scheduler = init_lr_scheduler(
            optim, C.optim.lr_scheduler,
            stepsize=C.optim.lr_decay_epoch,
            max_epoch=C.optim.max_epoch,
            last_epoch=iteration // epoch_size
        )
        lr_scheduler.load_state_dict(checkpoint['lr_scheduler'])
        del checkpoint

    else:
        lr_scheduler = init_lr_scheduler(
            optim,
            C.optim.lr_scheduler,
            stepsize=C.optim.lr_decay_epoch,
            max_epoch=C.optim.max_epoch
        )

        trainer = Trainer(
            device=device,
            model=model,
            optimizer=optim,
            lr_scheduler=lr_scheduler,
            train_loader=train_loader,
            val_loader=val_loader,
            out=outdir,
            iteration=iteration,
            epoch=epoch,
            bml=best_mean_loss,
            best_precision=best_precision,
            best_epoch=best_epoch,
            metrics_path=metrics_path,
        )

    try:
        trainer.train()

    except BaseException:
        if len(glob.glob(f"{outdir}/viz/*")) <= 1:
            shutil.rmtree(outdir)
        raise


if __name__ == "__main__":
    # print(git_hash())
    main()
