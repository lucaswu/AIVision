# AIVision Frontend

这是评片系统前端，基于 `React + Vite + Ant Design`。

## 常用命令

```bash
npm run dev
npm run test
npm run e2e
npm run build
npm run test:all
```

## 测试分层

- `npm run test`
  运行 `Vitest` 单元测试和组件测试，覆盖报告列表、评片页状态机、预览页筛选、缺陷保存/还原/历史栈等逻辑。
- `npm run e2e`
  运行 `Playwright` 浏览器冒烟测试，覆盖报告列表进入编辑、批量确认、对比模式切换、预览链路。
- `npm run test:all`
  依次执行 `unit/component + e2e`，其中 `e2e` 会先自动构建再启动 `vite preview`，适合作为上线前回归命令。

## 当前重点回归范围

- 报告列表、编辑页、预览页之间的主流程切换
- `ReportEditorPage` 的单图/对比模式选择逻辑
- 批量确认与进度刷新
- 缺陷记录保存 payload、后端数据 hydration、文件切换初始状态
- 缺陷历史栈：删除、重置、撤销、重做的核心语义
- 预览页统计与 `有缺陷 / 无缺陷` 过滤

## Playwright 说明

- 配置文件在 [playwright.config.ts](./playwright.config.ts)
- 用例在 [e2e/report-smoke.spec.ts](./e2e/report-smoke.spec.ts)
- 首次运行如果缺浏览器，可执行：

```bash
npx playwright install chromium
```

## CI

仓库已接入前端回归工作流：

- `npm test`
- `npm run e2e`
- `npm run build`

建议所有影响评片逻辑的改动，在合并前至少跑一次 `npm run test:all`。
