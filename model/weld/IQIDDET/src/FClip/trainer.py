import os
import time
import shutil
import os.path as osp
from timeit import default_timer as timer
import json

import numpy as np
import torch
import matplotlib as mpl
# mpl.use('Agg')
import matplotlib.pyplot as plt
from FClip.utils import recursive_to, ModelPrinter
from FClip.config import C
# os.environ['QT_QPA_PLATFORM'] = 'offscreen'


class Trainer(object):
    def __init__(
        self,
        device,
        model,
        optimizer,
        lr_scheduler,
        train_loader,
        val_loader,
        out,
        iteration=0,
        epoch=0,
        bml=1e1000,
        best_precision=0.0,
        best_epoch=-1,
        metrics_path=None,
    ):

        from FClip.visualize import VisualizeResults
        self.device = device

        self.model = model
        self.optim = optimizer
        self.lr_scheduler = lr_scheduler

        self.train_loader = train_loader
        self.val_loader = val_loader
        self.batch_size = C.model.batch_size
        self.eval_batch_size = C.model.eval_batch_size

        self.validation_interval = C.io.validation_interval

        self.out = out
        if not osp.exists(self.out):
            os.makedirs(self.out)

        self.epoch = epoch
        self.iteration = iteration
        self.max_epoch = C.optim.max_epoch
        self.lr_decay_epoch = C.optim.lr_decay_epoch
        self.num_stacks = C.model.num_stacks
        self.mean_loss = self.best_mean_loss = bml
        self.best_precision = best_precision
        self.best_epoch = best_epoch

        self.loss_labels = None
        self.acc_label = None
        self.avg_metrics = None
        self.metrics = np.zeros(0)
        self.visual = VisualizeResults()
        self.printer = ModelPrinter(out)
        self.metrics_path = metrics_path
        self.precision_head_written = False
        self.early_stop = getattr(C.io, "early_stop", None)
        self.no_improve = 0
        self.should_stop = False

    def _loss(self, result):
        losses = result["losses"]
        accuracy = result["accuracy"]
        # Don't move loss label to other place.
        # If I want to change the loss, I just need to change this function.
        if self.loss_labels is None:
            self.loss_labels = ["sum"] + list(losses[0].keys())
            self.acc_label = ["Acc"] + list(accuracy[0].keys())
            self.metrics = np.zeros([self.num_stacks, len(self.loss_labels)+len(self.acc_label)])

            self.printer.loss_head(loss_labels=self.loss_labels+self.acc_label)

        total_loss = 0
        for i in range(self.num_stacks):
            for j, name in enumerate(self.loss_labels):
                if name == "sum":
                    continue
                if name not in losses[i]:
                    assert i != 0
                    continue
                loss = losses[i][name].mean()
                self.metrics[i, 0] += loss.item()
                self.metrics[i, j] += loss.item()
                total_loss += loss

        for i in range(self.num_stacks):
            for j, name in enumerate(self.acc_label, len(self.loss_labels)):
                if name == "Acc":
                    continue
                if name not in accuracy[i]:
                    assert i != 0
                    continue
                acc = accuracy[i][name].mean()
                self.metrics[i, j] += acc.item()

        return total_loss

    def validate(self, isckpt=True):
        self.printer.tprint("Running validation...", " " * 55)
        training = self.model.training
        self.model.eval()

        total_loss = 0
        self.metrics[...] = 0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch_idx, (image, meta, target) in enumerate(self.val_loader):
                input_dict = {
                    "image": recursive_to(image, self.device),
                    "meta": recursive_to(meta, self.device),
                    "target": recursive_to(target, self.device),
                    "do_evaluation": True,
                }
                result = self.model(input_dict)
                total_loss += self._loss(result)

                if "heatmaps" in result and "count" in result["heatmaps"]:
                    pred = result["heatmaps"]["count"].argmax(1)
                    gt = target["count"].to(pred.device)
                    correct += (pred == gt).sum().item()
                    total += gt.numel()

                self.printer.tprint(
                    f"Validation [{batch_idx:5d}/{len(self.val_loader):5d}]",
                    " " * 25
                )

        precision = correct / max(total, 1)
        self.mean_loss = total_loss / len(self.val_loader)
        self.printer.valid_log(len(self.val_loader), self.epoch, self.iteration, self.batch_size, self.metrics[0])

        if not self.precision_head_written:
            self.printer.precision_head()
            self.precision_head_written = True
        self.printer.precision_log(self.epoch, self.iteration, self.batch_size, precision)

        if isckpt:
            torch.save(
                {
                    "iteration": self.iteration,
                    "arch": self.model.__class__.__name__,
                    "optim_state_dict": self.optim.state_dict(),
                    "model_state_dict": self.model.state_dict(),
                    "best_mean_loss": self.best_mean_loss,
                    "best_precision": self.best_precision,
                    "best_epoch": self.best_epoch,
                    'lr_scheduler': self.lr_scheduler.state_dict(),
                },
                osp.join(self.out, "checkpoint_lastest.pth.tar"),
            )
            if self.mean_loss < self.best_mean_loss:
                self.best_mean_loss = self.mean_loss
            improved = precision > self.best_precision
            if improved:
                self.best_precision = precision
                self.best_epoch = self.epoch
                shutil.copy(
                    osp.join(self.out, "checkpoint_lastest.pth.tar"),
                    osp.join(self.out, "checkpoint_best.pth.tar"),
                )
        else:
            improved = precision > self.best_precision

        if self.early_stop is not None:
            try:
                patience = int(self.early_stop)
            except Exception:
                patience = None
            if patience is not None and patience > 0:
                if improved:
                    self.no_improve = 0
                else:
                    self.no_improve += 1
                    if self.no_improve >= patience:
                        self.should_stop = True
                        self.printer.tprint(
                            f"Early stopping: no count precision improvement for {patience} validations.",
                            " " * 10,
                        )
                remaining = max(patience - self.no_improve, 0)
                self.printer.pprint(
                    f"early_stop: no_improve={self.no_improve}/{patience}, remaining={remaining}",
                    " " * 7,
                )
        self._write_metrics()

        if training:
            self.model.train()

    def _write_metrics(self):
        metrics_path = self.metrics_path or osp.join(self.out, "metrics.json")
        data = {
            "best_loss": float(self.best_mean_loss),
            "best_epoch": int(self.best_epoch),
            "best_precision": float(self.best_precision),
        }
        with open(metrics_path, "w") as f:
            json.dump(data, f)

    def train_epoch(self):
        self.model.train()

        time = timer()

        for batch_idx, (image, meta, target) in enumerate(self.train_loader):

            self.optim.zero_grad()
            self.metrics[...] = 0

            input_dict = {
                "image": recursive_to(image, self.device),
                "meta": recursive_to(meta, self.device),
                "target": recursive_to(target, self.device),
                "do_evaluation": False,
            }
            result = self.model(input_dict)

            loss = self._loss(result)
            if np.isnan(loss.item()):
                print("\n")
                print(self.metrics[0])
                raise ValueError("loss is nan while training")
            loss.backward()
            self.optim.step()

            if self.avg_metrics is None:
                self.avg_metrics = self.metrics
            else:
                self.avg_metrics[0, :len(self.loss_labels)] = self.avg_metrics[0, :len(self.loss_labels)] * 0.9 + \
                                                              self.metrics[0, :len(self.loss_labels)] * 0.1
                if len(self.loss_labels) < self.avg_metrics.shape[1]:
                    self.avg_metrics[0, len(self.loss_labels):] = self.metrics[0, len(self.loss_labels):]

            if self.iteration % 4 == 0:
                self.printer.train_log(self.epoch, self.iteration, self.batch_size, time, self.avg_metrics)

                time = timer()
            num_images = self.batch_size * self.iteration
            if num_images % self.validation_interval == 0 or num_images == 60:
                # record training loss
                if num_images > 0:
                    self.printer.valid_log(1, self.epoch, self.iteration, self.batch_size, self.avg_metrics[0],
                                           csv_name="train_loss.csv", isprint=False)
                    self.validate()
                    if self.should_stop:
                        return
                    time = timer()

            self.iteration += 1

    def train(self):
        plt.rcParams["figure.figsize"] = (24, 24)
        epoch_size = len(self.train_loader)
        start_epoch = self.iteration // epoch_size
        for self.epoch in range(start_epoch, self.max_epoch):
            self.train_epoch()
            if self.should_stop:
                break
            self.lr_scheduler.step()
