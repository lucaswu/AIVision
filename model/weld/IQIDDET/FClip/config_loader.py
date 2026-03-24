from FClip.box import Box
from FClip.config import C, M


def _ensure_box(obj, name):
    if name not in obj or obj[name] is None:
        obj[name] = Box()


def load_configs(model_yaml="config/model.yaml", params_yaml="params.yaml", ckpt=None):
    # reset C/M to avoid stale values
    try:
        C.clear()
        M.clear()
    except Exception:
        pass

    model_cfg = Box().from_yaml(filename=model_yaml)
    params_cfg = Box().from_yaml(filename=params_yaml)

    if model_cfg:
        C.update(model_cfg)

    _ensure_box(C, "io")
    _ensure_box(C, "model")
    _ensure_box(C, "optim")
    if "resume_from" not in C.io:
        C.io.resume_from = None
    if "model_initialize_file" not in C.io:
        C.io.model_initialize_file = None

    data = params_cfg.get("data", {})
    preprocess = params_cfg.get("preprocess", {})
    train = params_cfg.get("train", {})
    loss = params_cfg.get("loss", {})
    optim = params_cfg.get("optim", {})

    # io params
    if "processed_dir" in data:
        C.io.datadir = data.processed_dir
    if "dataname" in data:
        C.io.dataname = data.dataname
    if "logdir" in train:
        C.io.logdir = train.logdir
    if "num_workers" in train:
        C.io.num_workers = train.num_workers
    if "validation_interval" in train:
        C.io.validation_interval = train.validation_interval
    if "visual_num" in train:
        C.io.visual_num = train.visual_num
    if "run_name" in train:
        C.io.run_name = train.run_name
    if "early_stop" in train:
        C.io.early_stop = train.early_stop

    # model params
    if "batch_size" in train:
        C.model.batch_size = train.batch_size
    if "eval_batch_size" in train:
        C.model.eval_batch_size = train.eval_batch_size
    if "stage1" in train:
        C.model.stage1 = train.stage1
    if "delta" in train:
        C.model.delta = train.delta
    if "nlines" in train:
        C.model.nlines = train.nlines
    if "s_nms" in train:
        C.model.s_nms = train.s_nms

    if "heatmap_resolution" in preprocess:
        C.model.resolution = preprocess.heatmap_resolution
    if "input_resolution_h" in preprocess:
        C.model.input_resolution_h = preprocess.input_resolution_h
    if "input_resolution_w" in preprocess:
        C.model.input_resolution_w = preprocess.input_resolution_w
    if "crop" in preprocess:
        C.model.crop = preprocess.crop
    if "crop_factor" in preprocess:
        C.model.crop_factor = preprocess.crop_factor

    # loss weights
    if "head" in C.model:
        if "lcmap_weight" in loss:
            C.model.head.lcmap.loss_weight = loss.lcmap_weight
        if "lcoff_weight" in loss:
            C.model.head.lcoff.loss_weight = loss.lcoff_weight
        if "lleng_weight" in loss:
            C.model.head.lleng.loss_weight = loss.lleng_weight
        if "angle_weight" in loss:
            C.model.head.angle.loss_weight = loss.angle_weight
        if "count_weight" in loss:
            C.model.head.count.loss_weight = loss.count_weight
        if "count_sigma" in loss:
            C.model.head.count.sigma = loss.count_sigma

    # optim params
    if "name" in optim:
        C.optim.name = optim.name
    if "lr_scheduler" in optim:
        C.optim.lr_scheduler = optim.lr_scheduler
    if "lr_decay_epoch" in optim:
        C.optim.lr_decay_epoch = optim.lr_decay_epoch
    if "weight_decay" in optim:
        C.optim.weight_decay = optim.weight_decay
    if "amsgrad" in optim:
        C.optim.amsgrad = optim.amsgrad

    # train lr/max_epoch override optim if provided
    if "lr" in train:
        C.optim.lr = train.lr
    if "max_epoch" in train:
        C.optim.max_epoch = train.max_epoch
    if "lr" in optim and "lr" not in train:
        C.optim.lr = optim.lr
    if "max_epoch" in optim and "max_epoch" not in train:
        C.optim.max_epoch = optim.max_epoch

    if ckpt:
        C.io.model_initialize_file = ckpt

    M.update(C.model)
    return C, M, params_cfg
