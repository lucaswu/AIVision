  PYTHON_BIN=/home/cht/miniconda3/envs/weld-gpu/bin/python \
  REC_DATASET_DIR=/home/cht/code/IQIdet/local/OCRdatasets/iqi_rec_v1 \
  TRAIN_BATCH_SIZE=8 \
  EVAL_BATCH_SIZE=4 \
  EPOCH_NUM=50 \
  bash OCRtrain/tools/train_rec.sh