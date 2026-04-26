import { test, expect, type Page, type Route } from "@playwright/test";

const projectId = "project-1";
const taskId = "task-1";
const reportId = "report-1";
const userId = "user-1";

const pngBytes = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+X4sAAAAASUVORK5CYII=",
  "base64"
);

const jsonResponse = (data: unknown) => ({
  status: 200,
  contentType: "application/json; charset=utf-8",
  body: JSON.stringify({
    Code: 200,
    Message: "ok",
    Data: data,
  }),
});

const projects = [
  {
    Id: projectId,
    Name: "焊缝项目A",
    Description: "Playwright smoke",
    UserId: userId,
    CreateTime: "2026-04-26T09:00:00",
    Permission: "OWNER",
  },
];

const reports = [
  {
    ReportId: reportId,
    TaskId: taskId,
    TaskName: "焊缝检测任务-001",
    ProjectId: projectId,
    UserId: userId,
    ReportName: "焊缝检测报告-001",
    TotalFiles: 3,
    ConfirmedFiles: 1,
    TotalDefects: 1,
    SevereDefects: 0,
    NormalDefects: 1,
    Status: "PENDING",
    CreatedAt: "2026-04-26 10:00:00",
    UpdatedAt: "2026-04-26 10:00:00",
  },
];

const reportDetail = {
  ...reports[0],
  Status: "PENDING",
};

const defectRecord = {
  DefectRecordId: "defect-1",
  TaskFileId: "task-file-1",
  DefectName: "Porosity",
  Position: "中心偏左",
  Size: "3mm",
  Grade: "II",
  Remark: "冒烟测试缺陷",
  Geometry: JSON.stringify({ type: "rect", x: 220, y: 140, w: 120, h: 80 }),
};

const baseTaskFiles = [
  {
    TaskFileId: "task-file-1",
    FileId: "file-1",
    FileName: "film-001.png",
    Status: "completed",
    ReviewStatus: "CONFIRMED",
    VisionResult: JSON.stringify({
      metadata: { width: 640, height: 480 },
      results: [],
    }),
    ManualResult: "合格",
    PlateQuality: "A级",
    FilmPixelValue: "1024",
    Resolution: "4 lp/mm",
    Specification: "NB/T 47013",
    InspectionDate: "2026-04-26",
    WeldId: "W-01",
    FilmNumber: "P-001",
    FilmDensity: "2.5",
    Sensitivity: "1.8%",
    NormalizedSnr: "18.2",
    DefectRecords: [defectRecord],
    ProcessingEndTime: "2026-04-26T10:05:00",
    CorrectionRotation: 0,
    CorrectionFlip: false,
    WeldLocation: "[]",
    DefectPosition: "",
  },
  {
    TaskFileId: "task-file-2",
    FileId: "file-2",
    FileName: "film-002.png",
    Status: "completed",
    ReviewStatus: "PENDING",
    VisionResult: JSON.stringify({
      metadata: { width: 640, height: 480 },
      results: [],
    }),
    ManualResult: "",
    PlateQuality: "",
    FilmPixelValue: "",
    Resolution: "",
    Specification: "",
    InspectionDate: "",
    WeldId: "",
    FilmNumber: "",
    FilmDensity: "",
    Sensitivity: "",
    NormalizedSnr: "",
    DefectRecords: [],
    ProcessingEndTime: "2026-04-26T10:06:00",
    CorrectionRotation: 0,
    CorrectionFlip: false,
    WeldLocation: "[]",
    DefectPosition: "",
  },
  {
    TaskFileId: "task-file-3",
    FileId: "file-3",
    FileName: "film-003.png",
    Status: "completed",
    ReviewStatus: "PENDING",
    VisionResult: JSON.stringify({
      metadata: { width: 640, height: 480 },
      results: [],
    }),
    ManualResult: "",
    PlateQuality: "",
    FilmPixelValue: "",
    Resolution: "",
    Specification: "",
    InspectionDate: "",
    WeldId: "",
    FilmNumber: "",
    FilmDensity: "",
    Sensitivity: "",
    NormalizedSnr: "",
    DefectRecords: [],
    ProcessingEndTime: "2026-04-26T10:07:00",
    CorrectionRotation: 0,
    CorrectionFlip: false,
    WeldLocation: "[]",
    DefectPosition: "",
  },
];

const defectTypes = [
  { Code: "POR", Name: "Porosity", Color: "#fa8c16", SortOrder: 1, Enabled: true },
  { Code: "CRK", Name: "Crack", Color: "#ff4d4f", SortOrder: 2, Enabled: true },
];

let taskFiles = structuredClone(baseTaskFiles);
let batchConfirmCalls: string[][] = [];

function resetMockState() {
  taskFiles = structuredClone(baseTaskFiles);
  batchConfirmCalls = [];
}

async function fulfillApi(route: Route) {
  const url = new URL(route.request().url());
  const pathname = url.pathname;
  const method = route.request().method();

  if (pathname === "/api/v1/projects/list") {
    await route.fulfill(jsonResponse(projects));
    return;
  }

  if (pathname === "/api/v1/reports/list") {
    await route.fulfill(jsonResponse(reports));
    return;
  }

  if (pathname === `/api/v1/reports/${taskId}/detail`) {
    await route.fulfill(jsonResponse(reportDetail));
    return;
  }

  if (pathname === `/api/v1/reports/${taskId}/files`) {
    await route.fulfill(jsonResponse(taskFiles));
    return;
  }

  if (pathname === "/api/v1/reports/files/batch-confirm" && method === "POST") {
    const ids = (await route.request().postDataJSON()) as string[];
    batchConfirmCalls.push(ids);
    taskFiles = taskFiles.map((taskFile) =>
      ids.includes(taskFile.TaskFileId)
        ? { ...taskFile, ReviewStatus: "CONFIRMED" }
        : taskFile
    );
    await route.fulfill(jsonResponse(null));
    return;
  }

  if (pathname === "/api/v1/defect-types") {
    await route.fulfill(jsonResponse(defectTypes));
    return;
  }

  if (pathname === `/api/v1/defect-records/task-file/task-file-1`) {
    await route.fulfill(jsonResponse([defectRecord]));
    return;
  }

  if (pathname === `/api/v1/defect-records/task-file/task-file-2`) {
    await route.fulfill(jsonResponse([]));
    return;
  }

  if (pathname === `/api/v1/defect-records/task-file/task-file-3`) {
    await route.fulfill(jsonResponse([]));
    return;
  }

  if (pathname === `/api/v1/users/${userId}`) {
    await route.fulfill(
      jsonResponse({
        userId,
        username: "测试质检员",
        email: "qa@example.com",
        role: "QC",
        projects: [projectId],
        createTime: "2026-04-01T09:00:00",
        lastLoginTime: "2026-04-26T09:50:00",
        status: "ACTIVE",
      })
    );
    return;
  }

  if (pathname === "/api/v1/files/preview" || pathname === "/api/v1/files/thumbnail") {
    await route.fulfill({
      status: 200,
      contentType: pathname.endsWith("/thumbnail") ? "image/jpeg" : "image/png",
      body: pngBytes,
    });
    return;
  }

  await route.fulfill({
    status: 404,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify({
      Code: 404,
      Message: `Unhandled mock for ${pathname}`,
      Data: null,
    }),
  });
}

async function bootstrap(page: Page) {
  await page.addInitScript(([authUserId]) => {
    localStorage.setItem("token", "playwright-token");
    localStorage.setItem("userId", authUserId);
    localStorage.setItem("username", "测试质检员");
    localStorage.setItem("role", "QC");
  }, [userId]);

  await page.route("**/api/v1/**", fulfillApi);
}

test.describe("报告管理 smoke", () => {
  test.beforeEach(() => {
    resetMockState();
  });

  test("can navigate from report list to editor and preview", async ({ page }) => {
    await bootstrap(page);

    await page.goto(`/projects/${projectId}/reports`);

    await expect(page.getByRole("heading", { name: "报告管理" })).toBeVisible();
    await expect(page.getByText("焊缝检测报告-001")).toBeVisible();

    await page.getByRole("button", { name: "审核" }).click();

    await expect(page.getByText("返回列表")).toBeVisible();
    await expect(page.getByText("当前为单图模式")).toBeVisible();
    await expect(page.getByText("film-001.png")).toBeVisible();

    await page.getByRole("button", { name: "预览报告" }).click();

    await expect(page.getByRole("heading", { name: /检测报告/ })).toBeVisible();
    await expect(page.getByText("1. 缺陷总览")).toBeVisible();
    await expect(page.getByText("2. 详细检测结果")).toBeVisible();
    await page.getByText("film-001.png").click();
    await expect(page.getByText("缺陷类型: Porosity")).toBeVisible();
  });

  test("can batch confirm selected files from the editor", async ({ page }) => {
    await bootstrap(page);

    await page.goto(`/projects/${projectId}/reports`);
    await page.getByRole("button", { name: "审核" }).click();

    await expect(page.getByText("33%")).toBeVisible();

    await page.getByRole("checkbox", { name: "全选" }).check();
    await page.getByRole("button", { name: "批量确认 (3)" }).click();

    await expect.poll(() => batchConfirmCalls.length).toBe(1);
    await expect.poll(() => taskFiles.every((file) => file.ReviewStatus === "CONFIRMED")).toBe(
      true
    );
    await expect(page.getByText("100%")).toBeVisible();
    await expect(page.getByRole("button", { name: "批量确认 (3)" })).toBeHidden();
  });

  test("can switch to compare mode and fill the second comparison slot", async ({ page }) => {
    await bootstrap(page);

    await page.goto(`/projects/${projectId}/reports`);
    await page.getByRole("button", { name: "审核" }).click();

    await expect(page.getByText("当前为单图模式")).toBeVisible();

    await page.getByRole("switch").click();

    await expect(page.getByText("当前为对比模式")).toBeVisible();
    await expect(page.getByText("请在左侧选择图片 2")).toBeVisible();

    await page.getByText("film-002.png").click();

    await expect(page.getByText("请在左侧选择图片 2")).toBeHidden();
  });

  test("resets compare mode when a third file is selected", async ({ page }) => {
    await bootstrap(page);

    await page.goto(`/projects/${projectId}/reports`);
    await page.getByRole("button", { name: "审核" }).click();
    await page.getByRole("switch").click();

    await page.getByText("film-002.png").click();
    await expect(page.getByText("请在左侧选择图片 2")).toBeHidden();

    await page.getByText("film-003.png").click();

    await expect(page.getByText("请在左侧选择图片 2")).toBeVisible();
  });
});
