# IQI 等级识别交付说明

本文档面向集成同事，说明如何调用本工程的交付接口，以及如何解析新增后的 JSON 输出。

## 1. 交付入口

交付脚本：

- `run_iqi_grade_infer.py`

支持输入：

- `--image-path`
- `--image-dir`
- `--image-list`

输出：

- 一个批量 JSON 文件

## 2. 当前交付逻辑

当前交付逻辑分两层：

1. 全图 OCR 层
- 在整图上完成：
  - 文本检测
  - 文本矫正
  - 文本识别
- 从 OCR 结果中提取：
  - 焊道号
  - 片号
  - 检测部件代号
  - 管道规格
  - 像质计标识

2. IQI 主任务层
- 只有当全图 OCR 成功匹配到合法像质计标识时，才会继续执行：
  - ROI 检测
  - ROI 增强
  - FClip 像质丝识别
  - 等级计算

说明：

- `ok/result_code` 只表示 IQI 主任务是否成功
- 即使焊道号 / 片号识别成功，只要 IQI 标识或等级失败，`ok` 仍然可能是 `false`

## 3. 注意事项

交付脚本不再包含整图方向矫正参数：

- 不支持 `--enable-correction`
- 不支持 `--correction-model`

原因：

- 集成侧上游工程会先完成整图矫正
- 本交付接口只负责全图 OCR、IQI ROI、像质丝识别和等级输出

如果需要调试整图方向矫正，请使用：

- `run_inference_pipeline.py`

## 4. 模型路径

当前交付所需模型都放在：

- `models/`

主要使用：

- `models/guagerotation.pt`
- `models/fclip67.pth.tar`
- `models/fclip_config.yaml`
- `models/OCR_rec_inference_best_accuracy`
- `models/ocr_orientation_model.pth`

## 5. 推荐调用方式

### 5.1 目录批量

```bash
cd /home/cht/code/IQIdet

/home/cht/miniconda3/envs/weld-gpu/bin/python run_iqi_grade_infer.py \
  --image-dir IQIdata/ori/img \
  --gauge-weights models/guagerotation.pt \
  --fclip-ckpt models/fclip67.pth.tar \
  --fclip-config models/fclip_config.yaml \
  --output-json outputs/iqi_grade_infer/iqi_grade_results.json \
  --ocr-det-model-name PP-OCRv5_server_det \
  --ocr-rec-model-dir models/OCR_rec_inference_best_accuracy \
  --enable-ocr-orientation \
  --ocr-orientation-model models/ocr_orientation_model.pth \
  --ocr-orientation-device cuda:0 \
  --ocr-number-range 6,10-15
```

### 5.2 路径列表批量

```bash
/home/cht/miniconda3/envs/weld-gpu/bin/python run_iqi_grade_infer.py \
  --image-list images.txt \
  --gauge-weights models/guagerotation.pt \
  --fclip-ckpt models/fclip67.pth.tar \
  --fclip-config models/fclip_config.yaml \
  --output-json outputs/iqi_grade_infer/from_list.json \
  --ocr-det-model-name PP-OCRv5_server_det \
  --ocr-rec-model-dir models/OCR_rec_inference_best_accuracy \
  --ocr-number-range 6,10-15
```

## 6. 当前字段规则

### 6.1 焊道号 / 片号

规则：

- `数字(+|-)数字+可选字母`
- 例如：
  - `66+2Y`
  - `28+3`

输出时会拆成：

- `weld_numbers`
- `film_numbers`

同时也保留原始配对：

- `weld_film_pairs`

### 6.2 检测部件代号

规则：

- `数字 + S/R + 数字`
- 例如：
  - `4S9`
  - `4R11`

### 6.3 管道规格

规则：

- `数字 + X/x/× + 数字`
- 例如：
  - `57X12`
  - `57×12`

### 6.4 像质计标识

继续沿用当前 IQI 规则：

- `FE` -> `uniform`
- `NI` -> `gradient`
- `E+J` -> `uniform`
- `I+J` -> `gradient`

数字范围：

- 默认允许：`6,10-15`
- 单数字 `6` 会被标准化成 `06`
- 可通过 `--ocr-number-range` 修改

## 7. 输出 JSON 结构

顶层结构：

```json
{
  "schema": "iqi_grade_batch_v1",
  "ok": true,
  "fatal_error": null,
  "meta": {},
  "summary": {},
  "results": []
}
```

## 8. summary 字段

当前 summary 主要包含：

- `images_total`
- `success_total`
- `failure_total`
- `result_code_hist`
- `result_code_hist_named`
- `iqi_type_hist`
- `grade_hist`
- `field_totals`
- `images_with_general_fields`
- `images_with_iqi_marker`

## 9. results 单图字段

每个 `results[i]` 的关键字段：

- `image_path`
- `ok`
- `result_code`
- `result_name`
- `result_message`
- `grade`
- `iqi_type`
- `plate_code`
- `plate_number`
- `wire_count`
- `general_fields_found`
- `iqi_marker_found`
- `roi`
- `plate`
- `fields`
- `field_statistics`
- `wire`
- `warnings`
- `errors`

## 10. fields 字段说明

新增后的 `fields` 结构如下：

```json
"fields": {
  "component_codes": [],
  "weld_film_pairs": [],
  "weld_numbers": [],
  "film_numbers": [],
  "pipe_specs": []
}
```

### 10.1 component_codes

每项示例：

```json
{
  "text": "4S9",
  "match_text": "4S9",
  "value": "4S9",
  "score": 0.98,
  "box": [[...]],
  "crop_index": 3
}
```

### 10.2 weld_film_pairs

每项示例：

```json
{
  "text": "66+2Y",
  "match_text": "66+2Y",
  "weld_no": "66",
  "film_no": "2Y",
  "separator": "+",
  "score": 0.99,
  "box": [[...]],
  "crop_index": 5
}
```

### 10.3 weld_numbers

每项示例：

```json
{
  "text": "66+2Y",
  "match_text": "66+2Y",
  "value": "66",
  "score": 0.99,
  "box": [[...]],
  "crop_index": 5
}
```

### 10.4 film_numbers

每项示例：

```json
{
  "text": "66+2Y",
  "match_text": "66+2Y",
  "value": "2Y",
  "score": 0.99,
  "box": [[...]],
  "crop_index": 5
}
```

### 10.5 pipe_specs

每项示例：

```json
{
  "text": "57X12",
  "match_text": "57X12",
  "value": "57X12",
  "outer_diameter": "57",
  "wall_thickness": "12",
  "score": 0.97,
  "box": [[...]],
  "crop_index": 7
}
```

## 11. field_statistics 字段说明

示例：

```json
"field_statistics": {
  "component_code_count": 1,
  "weld_film_pair_count": 1,
  "weld_number_count": 1,
  "film_number_count": 1,
  "pipe_spec_count": 1,
  "general_fields_found": true,
  "iqi_marker_found": true
}
```

## 12. 成功结果示例

```json
{
  "image_path": "/abs/path/a.png",
  "ok": true,
  "result_code": 0,
  "result_name": "success",
  "result_message": "识别成功",
  "grade": 12,
  "iqi_type": "uniform",
  "plate_code": "FE12JB",
  "plate_number": 12,
  "wire_count": 3,
  "general_fields_found": true,
  "iqi_marker_found": true,
  "fields": {
    "component_codes": [{"value": "4S9"}],
    "weld_film_pairs": [{"weld_no": "66", "film_no": "2Y"}],
    "weld_numbers": [{"value": "66"}],
    "film_numbers": [{"value": "2Y"}],
    "pipe_specs": [{"value": "57X12", "outer_diameter": "57", "wall_thickness": "12"}]
  },
  "wire": {
    "status": "ok",
    "wire_count": 3,
    "parsed_line_count": 3,
    "lines": []
  }
}
```

## 13. 失败结果说明

若全图字段识别成功，但 IQI 主任务失败，结果可能是：

- `fields` 中已有焊道号 / 片号等内容
- `ok` 仍然为 `false`
- `result_code` 仍表示 IQI 主任务失败原因

例如：

- 已识别到焊道号和片号
- 但没有合法像质计标识
- 则仍可能返回：
  - `2002 marker_missing_jb`
  - `2004 marker_type_unknown`
  - `2005 marker_number_missing`
  - `2007 marker_number_out_of_range`

## 14. 集成侧推荐解析方式

集成侧建议分两层读取：

1. 读取 IQI 主任务结果
- `ok`
- `result_code`
- `grade`
- `iqi_type`
- `plate_code`
- `wire_count`

2. 读取通用字段结果
- `fields.weld_numbers`
- `fields.film_numbers`
- `fields.component_codes`
- `fields.pipe_specs`

推荐逻辑：

1. 若 `ok == true` 且 `result_code == 0`，则 IQI 主任务成功
2. `grade` 为最终像质计等级
3. 即使 `ok == false`，也仍然可以从 `fields` 中读取已成功识别的焊道号、片号等信息
4. 若需要查看失败原因，直接看 `result_name` 和 `result_message`
