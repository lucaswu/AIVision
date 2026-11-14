# 第三方报告系统对接接口文档

## 1. 概述
本文档描述第三方报告系统如何对接 AI Vision 检测系统，获取详细的检测报告数据，包括焊口编号、工艺参数和缺陷评定详情。

**通用约定**

- 所有接口都要在请求头携带 `project-id`（项目 ID）和 `user-id`（用户 ID）。系统会校验该用户是否有该项目的访问权限。
- 响应统一使用如下结构：

```json
{ "Code": 200, "Message": "获取成功", "Data": { ... } }
```

- HTTP 状态码与 `Code` 字段一致：

| Code | 含义 |
| :--- | :--- |
| 200 | 成功 |
| 400 | 参数错误（如 `scope` 取值非法） |
| 403 | 无该项目的访问权限 |
| 404 | 任务不存在，或任务不属于请求头中的项目 |
| 500 | 服务内部错误 |

## 2. 核心流程：如何获取 Task ID

调用报告详情接口前，需要先拿到任务 ID (`TaskId`)。按业务场景分两种方式：

### 方式一：主动查询模式（推荐，适用于第三方定期拉取数据）
适用于第三方系统定期从 AI 系统同步最新完成的检测任务。

1. 调用**任务列表接口** `GET /api/v1/tasks/list`。
2. 按 `CreateTime`（创建时间）或 `EndTime`（完成时间）筛选最近的任务。
3. 只保留 `Status` 为 `completed`（已完成）的任务。
4. 取出列表项中的 `Id`，作为 `task_id` 调用报告详情接口。

### 方式二：发起端模式（适用于第三方触发检测）
适用于第三方系统直接调用 API 发起检测的场景。

1. 调用 `POST /api/v1/files/upload` 上传底片图像，从响应中拿到每个文件的 `FileId`。
2. 调用**提交任务接口** `POST /api/v1/tasks/submit`，响应中直接返回新生成的 `TaskId`。
3. 轮询**任务状态接口** `GET /api/v1/tasks/{task_id}/status`，直到 `Status` 变为 `completed`（或 `failed`）。
4. 调用报告详情接口获取结果。

---

## 3. 接口定义

### 3.1 任务列表

- **接口地址**：`GET /api/v1/tasks/list`

| 参数名 | 位置 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| project-id | Header | String | 是 | 项目 ID |
| user-id | Header | String | 是 | 用户 ID |
| scope | Query | String | 否 | `mine`（默认）：只返回该用户自己创建的任务，用户需要有项目的编辑权限；`all`：返回项目下所有用户的任务，用户有项目的读权限即可 |

**响应示例**

```json
{
  "Code": 200,
  "Message": "获取成功",
  "Data": {
    "Tasks": [
      {
        "Id": "e89dab68-db3a-4e1f-8c69-16036f32e2d4",
        "Name": "2023-10-27-检测任务A",
        "ProjectId": "proj-001",
        "UserId": "user-001",
        "AlgorithmType": "object-detection",
        "Status": "completed",
        "Progress": 100,
        "FileCount": 12,
        "ProcessedFiles": 12,
        "SuccessFiles": 12,
        "FailedFiles": 0,
        "CreateTime": "2023-10-27 10:00:00",
        "UpdateTime": "2023-10-27 10:05:12",
        "EndTime": "2023-10-27 10:05:12",
        "IsArchived": false
      }
    ],
    "TotalCount": 1
  }
}
```

`Status` 取值：`pending`（排队中）、`processing`（检测中）、`completed`（已完成）、`failed`（失败）。

### 3.2 提交检测任务

- **接口地址**：`POST /api/v1/tasks/submit`

**请求体示例**

```json
{
  "Name": "2023-10-27-检测任务A",
  "Description": "",
  "AlgorithmType": "object-detection",
  "SelectedFiles": [ { "FileId": "file-uuid-001" } ]
}
```

还可以用 `DirectoryIds`（目录 ID 列表）或 `ProjectIds`（项目 ID 列表）批量选择文件，三种方式可以组合使用。

**响应示例**

```json
{
  "Code": 200,
  "Message": "任务提交成功",
  "Data": { "TaskId": "e89dab68-...", "Status": "pending", "FileCount": 1, "Timestamp": "..." }
}
```

### 3.3 获取详细报告结果

该接口返回生成正式报告所需的完整结构化数据。

- **接口地址**：`GET /api/v1/tasks/{task_id}/report-result`

| 参数名 | 位置 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| task_id | Path | String | 是 | 任务 ID |
| project-id | Header | String | 是 | 项目 ID，必须是该任务所属的项目 |
| user-id | Header | String | 是 | 用户 ID，需要有该项目的读权限 |

**响应示例**

```json
{
  "Code": 200,
  "Message": "获取成功",
  "Data": {
    "TaskId": "e89dab68-db3a-4e1f-8c69-16036f32e2d4",
    "TaskName": "2023-10-27-检测任务A",
    "ProjectId": "proj-001",
    "ProjectName": "某管线项目",
    "Status": "completed",
    "CreateTime": "2023-10-27 10:00:00",
    "EndTime": "2023-10-27 10:05:12",
    "Total": 1,
    "ReportItems": [
      {
        "FileId": "file-uuid-001",
        "FileName": "A14.bmp",

        "WeldNo": "HJ-001",
        "SliceNo": "3-4",
        "FilmDensity": "2.5",
        "IQISensitivity": "W12",
        "NormalizedSnr": "",
        "FilmPixelValue": "",
        "Resolution": "",
        "Specification": "",
        "InspectionDate": "",

        "QualityLevel": "II级",
        "EvaluationResult": "合格",
        "Remark": null,

        "Defects": [
          {
            "DefectId": "1",
            "DefectNature": "气孔",
            "DefectLocation": "X:120, Y:300",
            "DefectBBox": [100, 280, 140, 320],
            "DefectSize": "3.5mm",
            "DefectLevel": "I",
            "Remark": ""
          },
          {
            "DefectId": "2",
            "DefectNature": "夹渣",
            "DefectLocation": "距焊口起点 120mm",
            "DefectBBox": [430, 300, 470, 320],
            "DefectSize": "8mm",
            "DefectLevel": "II",
            "Remark": "需复评"
          }
        ]
      }
    ]
  }
}
```

**ReportItems 字段说明**

| 字段 | 说明 |
| :--- | :--- |
| FileId / FileName | 底片文件 ID 和原始文件名 |
| WeldNo | 焊口编号 |
| SliceNo | 片号 |
| FilmDensity | 底片黑度 |
| IQISensitivity | 像质计灵敏度 |
| NormalizedSnr | 归一化信噪比 |
| FilmPixelValue / Resolution / Specification / InspectionDate | 底片像素值、分辨率、规格、检测日期 |
| QualityLevel | 质量等级 |
| EvaluationResult | 综合评定结果 |
| Remark | 整片备注 |
| Defects | 缺陷列表，见下表 |

**Defects 字段说明**

| 字段 | 说明 |
| :--- | :--- |
| DefectId | 缺陷 ID |
| DefectNature | 缺陷性质 |
| DefectLocation | 缺陷位置 |
| DefectBBox | 缺陷外接矩形 `[x1, y1, x2, y2]`，原图像素坐标；没有几何信息时为 `null` |
| DefectSize | 缺陷尺寸 |
| DefectLevel | 单个缺陷分级 |
| Remark | 缺陷备注 |

### 3.4 字段业务说明

1. **一张底片可能对应多条 ReportItem**
   - 一张底片上可能有多个焊口，每个焊口返回一条 `ReportItem`，`Defects` 只包含属于该焊口的缺陷。
   - 底片还没有配置焊口时，返回一条 `ReportItem`，`WeldNo` 为 `null`，包含该底片的全部缺陷。
   - 底片已经配置了焊口，但有缺陷没分配到任何焊口时，会额外返回一条 `WeldNo` 为 `null` 的 `ReportItem`，承载这些"未分组"缺陷，避免遗漏。

2. **焊口编号 (WeldNo) / 片号 (SliceNo)**
   - 优先返回人工在"审核页面"录入或修正后的数据。
   - 没有人工审核时，返回 OCR 从底片图像上自动识别的结果；识别失败时为 `null`。

3. **缺陷位置 (DefectLocation / DefectBBox)**
   - 人工在审核页面填写过位置描述时，`DefectLocation` 返回该描述。
   - 否则 `DefectLocation` 返回缺陷外接矩形中心点的图像坐标，格式为 `X:中心x, Y:中心y`。
   - 第三方要绘制缺陷分布示意图时，建议直接使用 `DefectBBox`。

4. **缺陷性质 (DefectNature)**
   - 返回 AI 模型识别结果映射后的缺陷类型名称，例如"气孔""夹渣""裂纹"。
   - 经过人工审核的，返回人工确认后的最终缺陷类型。

5. **综合评定结果 (EvaluationResult)**
   - 有人工评定结果时，返回人工结果。
   - 人工已确认但没有填写评定结果时，返回"合格"。
   - 其余情况：检测已完成返回"待评定"，否则返回"检测中"。

---

## 4. 附：跨任务查询（按焊口编号）

如果需要跨任务、按焊口编号查询，可以使用 `POST /api/v1/tasks/report-result`。

- 请求头只需要 `user-id`。
- 请求体格式为 `{"projectIds": ["..."], "weldNos": ["HJ-001"]}`，`weldNos` 可以不传。
- 返回的 `Data.ReportItems` 结构与 3.3 相同，但不包含任务级字段（TaskId、TaskName 等）。
