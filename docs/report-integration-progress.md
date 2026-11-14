# 第三方报告对接 API：进度记录

> 对接接口文档：[report-integration-api.md](../report-integration-api.md)
> 分支：`deploy`　最后更新：2026-11-14

## 1. 已确认的决策

| 问题 | 结论 |
| :--- | :--- |
| 任务列表字段名、状态值与文档不一致 | **改文档，不改代码**。列表字段用 `Id`，状态值用 `pending / processing / completed / failed` |
| 焊口号、片号从文件名兜底解析 | **暂不做**。代码里没有这个逻辑，实际兜底来源是 OCR 从图像识别，文档已改成这样描述 |
| 鉴权（API Key 等） | **暂不做**。内部系统，沿用 `project-id` + `user-id` 两个请求头 |
| 任务列表范围 | 默认只返回该用户自己创建的任务；传 `scope=all` 返回项目下所有用户的任务 |

## 2. 已完成（代码已提交，未编译验证）

- [x] 新增 `GET /api/v1/tasks/{task_id}/report-result`
  - 入口：`TaskController.getTaskReportResultByTask`，实现：`TaskService.getTaskReportResultByTask`
  - 返回 DTO：`model/TaskReportResultResponse.java`
  - 有项目读权限即可查询，不要求是任务创建人；任务不属于请求头中的项目时返回 404
  - 错误码：400 参数错误 / 403 无权限 / 404 不存在 / 500 其他错误
- [x] 底片按焊口展开的逻辑抽成 `expandReportItems`，新 GET 接口和原有的 `POST /api/v1/tasks/report-result` 共用
- [x] 文件名改为批量查询（`loadFileNames`），去掉逐条 `findById` 的 N+1 查询
- [x] 缺陷位置
  - 新增 `DefectBBox` 字段，格式 `[x1, y1, x2, y2]`
  - `DefectLocation`：人工填写的 position 优先，否则返回外接矩形中心点 `X:cx, Y:cy`
  - geometry 解析在 `TaskService.geometryToBBox`，支持 rect、数组、points 多边形三种格式
- [x] `GET /api/v1/tasks/list` 新增 `scope` 参数（`mine` / `all`），非法值返回 400
- [x] 单元测试：`src/test/.../service/TaskServiceReportResultTest.java`，共 10 个用例
- [x] 接口文档 `report-integration-api.md` 已与代码对齐

## 3. 待办（换电脑后从这里继续）

1. **编译并跑测试**（最优先）。原来的电脑没有 JDK 和 Maven，代码一次都没编译过。
   ```bash
   cd backEnd/api_gateway
   mvn -q compile
   mvn test -Dtest=TaskServiceReportResultTest
   mvn test   # 全量测试
   ```
   测试编译失败或用例失败时，先修这部分。
2. **检查原有的 `TaskServiceTest`**。它没有 mock `userRepository` 和 `permissionRepository`，执行权限校验时可能空指针。这个问题在本次改动之前就存在；如果确实失败，补上这两个 `@Mock` 即可。
3. **联调验证**：启动服务后用真实数据调一遍。
   ```bash
   curl -H "project-id: <pid>" -H "user-id: <uid>" "http://<host>/api/v1/tasks/list?scope=all"
   curl -H "project-id: <pid>" -H "user-id: <uid>" "http://<host>/api/v1/tasks/<taskId>/report-result"
   ```
   重点核对以下几项：
   - `DefectBBox` 的坐标与审核页上标注框的位置是否一致。geometry 存的是原图坐标还是旋转/翻转校正后的坐标？需要对照 `correction_rotation` / `user_rotation` 确认。
   - 多焊口底片的展开结果，以及"未分组"那一条是否正确。
   - 403 和 404 的返回是否符合预期。
4. **前端或网关**：确认 nginx / 网关会转发 `GET /api/v1/tasks/*/report-result`。现有的 `/api/v1/tasks/` 前缀规则应该已经覆盖，需要实际验证一下。
5. **把接口文档交给第三方**，并把 `TaskId` 的获取方式确定为文档第 2 节中的方式一或方式二。

## 4. 暂缓（已确认先不做，后续如有需要再做）

- 焊口号、片号从文件名解析兜底。需要先拿到客户的文件命名规则，例如 `HJ-001_3-4.bmp`。
- 第三方接口鉴权（如 `X-Api-Key` 请求头，Key 配置在 `application.yml`）。
- `EvaluationResult` 的业务规则：现在"人工已确认但没填结果"时默认返回"合格"，需要业务方确认这个规则。
- 整片 `Remark` 现在返回的是 `task_file.error_message`，并不是真正的人工备注。如果第三方需要人工备注，要新增字段并在审核页提供录入入口。
