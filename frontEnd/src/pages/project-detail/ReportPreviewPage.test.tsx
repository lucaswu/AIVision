import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportPreviewPage from "./ReportPreviewPage";
import type { TaskFile } from "../../utils/data";

const { useRequestMock, reportApiMocks, userApiMocks, messageMocks } = vi.hoisted(() => ({
  useRequestMock: vi.fn(),
  reportApiMocks: {
    getReportDetail: vi.fn(),
    getReportFiles: vi.fn(),
    downloadReport: vi.fn(),
  },
  userApiMocks: {
    getUser: vi.fn(),
  },
  messageMocks: {
    info: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock("ahooks", () => ({
  useRequest: useRequestMock,
}));

vi.mock("../../utils/api", () => ({
  reportAPI: reportApiMocks,
  userAPI: userApiMocks,
  getUserId: () => "user-1",
}));

vi.mock("@/components/HighBitPreviewImage", () => ({
  default: ({ alt = "preview", fileName }: { alt?: string; fileName?: string }) => (
    <img alt={alt} data-filename={fileName} />
  ),
}));

vi.mock("antd", () => {
  const Layout = ({ children, ...props }: any) => <div {...props}>{children}</div>;
  Layout.Content = ({ children, ...props }: any) => <div {...props}>{children}</div>;
  Layout.Sider = ({ children, ...props }: any) => <aside {...props}>{children}</aside>;

  const Button = ({ children, icon, onClick, type: _type, block: _block, ...props }: any) => (
    <button type="button" onClick={onClick} {...props}>
      {icon}
      {children}
    </button>
  );

  const Typography = {
    Title: ({ children, level: _level, ...props }: any) => <h2 {...props}>{children}</h2>,
    Text: ({ children, strong: _strong, type: _type, ...props }: any) => <span {...props}>{children}</span>,
    Paragraph: ({ children, ...props }: any) => <p {...props}>{children}</p>,
  };

  const Space = ({ children, ...props }: any) => <div {...props}>{children}</div>;
  const Tag = ({ children }: any) => <span>{children}</span>;
  const Row = ({ children }: any) => <div>{children}</div>;
  const Col = ({ children }: any) => <div>{children}</div>;
  const Divider = () => <hr />;
  const Breadcrumb = ({ items }: any) => <nav>{items.map((item: any) => item.title).join(" / ")}</nav>;
  const Tooltip = ({ children }: any) => <>{children}</>;
  const Image = (props: any) => <img {...props} alt={props.alt || "image"} />;
  const Modal = ({ open, children }: any) => (open ? <div>{children}</div> : null);
  const Card = ({ children }: any) => <section>{children}</section>;
  const Table = ({ children }: any) => <div>{children}</div>;
  const Statistic = ({ title, value }: any) => <div>{`${title}:${value}`}</div>;
  const Tabs = ({ children }: any) => <div>{children}</div>;
  const List = ({ dataSource = [], renderItem, loading }: any) => (
    <div data-loading={loading ? "true" : "false"}>
      {dataSource.map((item: any, index: number) => (
        <React.Fragment key={item.TaskFileId ?? index}>{renderItem(item)}</React.Fragment>
      ))}
    </div>
  );
  const Collapse = ({ children }: any) => <div>{children}</div>;
  Collapse.Panel = ({ header, children }: any) => (
    <section>
      <div>{header}</div>
      <div>{children}</div>
    </section>
  );

  return {
    Card,
    Typography,
    Space,
    Tag,
    Button,
    message: messageMocks,
    Table,
    Row,
    Col,
    Statistic,
    Divider,
    List,
    Tabs,
    Layout,
    Collapse,
    Breadcrumb,
    Tooltip,
    Image,
    Modal,
  };
});

function buildFile(index: number, overrides: Partial<TaskFile> = {}): TaskFile {
  return {
    TaskFileId: `task-file-${index}`,
    FileId: `file-${index}`,
    FileName: `film-00${index}.png`,
    Status: "completed",
    ReviewStatus: index < 3 ? "CONFIRMED" : "PENDING",
    VisionResult: JSON.stringify({ metadata: { width: 640, height: 480 }, results: [] }),
    ProcessingEndTime: "2026-04-26T10:00:00",
    DefectRecords: [],
    ...overrides,
  };
}

const reportResponse = {
  Code: 200,
  Message: "ok",
  Data: {
    ReportId: "report-1",
    TaskId: "task-1",
    TaskName: "焊缝检测任务-001",
    ProjectId: "project-1",
    UserId: "user-1",
    ReportName: "焊缝报告",
    TotalFiles: 3,
    ConfirmedFiles: 2,
    TotalDefects: 1,
    SevereDefects: 0,
    NormalDefects: 1,
    Status: "PENDING" as const,
    CreatedAt: "2026-04-26T10:00:00",
    UpdatedAt: "2026-04-26T10:00:00",
  },
};

const userResponse = {
  Code: 200,
  Message: "ok",
  Data: {
    userId: "user-1",
    username: "测试质检员",
    email: "qa@example.com",
    role: "QC",
    projects: ["project-1"],
    createTime: "2026-04-01T09:00:00",
    lastLoginTime: "2026-04-26T09:50:00",
    status: "ACTIVE",
  },
};

describe("ReportPreviewPage", () => {
  const files = [
    buildFile(1, {
      DefectRecords: [
        {
          DefectRecordId: "defect-1",
          TaskFileId: "task-file-1",
          DefectName: "Porosity",
          Position: "中心",
          Size: "3mm",
          Grade: "II",
          Remark: "note",
          Geometry: JSON.stringify({ type: "rect", x: 10, y: 20, w: 30, h: 40 }),
        },
      ],
    }),
    buildFile(2),
    buildFile(3, { ReviewStatus: "PENDING" }),
  ];

  beforeEach(() => {
    useRequestMock.mockReset();
    messageMocks.info.mockReset();
    reportApiMocks.downloadReport.mockReturnValue("/download/report-1");

    useRequestMock.mockImplementation((service: () => unknown) => {
      const source = service.toString();

      if (source.includes("getReportDetail")) {
        return { data: reportResponse };
      }

      if (source.includes("getUser")) {
        return { data: userResponse };
      }

      if (source.includes("getReportFiles")) {
        return {
          data: {
            Code: 200,
            Message: "ok",
            Data: files,
          },
          loading: false,
        };
      }

      return {};
    });
  });

  it("renders stats and filters files by defect presence", async () => {
    const user = userEvent.setup();

    render(
      <ReportPreviewPage
        taskId="task-1"
        projectId="project-1"
        projectName="焊缝项目"
        onBack={vi.fn()}
        onReview={vi.fn()}
      />
    );

    expect(await screen.findByText("焊缝检测任务-001 - 检测报告")).toBeInTheDocument();
    expect(screen.getByText("已确认文件")).toBeInTheDocument();
    expect(screen.getByText("未确认文件")).toBeInTheDocument();
    expect(screen.getByText("缺陷统计")).toBeInTheDocument();

    expect(screen.getByText("film-001.png")).toBeInTheDocument();
    expect(screen.getByText("film-002.png")).toBeInTheDocument();
    expect(screen.getByText("film-003.png")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "有缺陷 (1)" }));

    expect(screen.getByText("film-001.png")).toBeInTheDocument();
    expect(screen.queryByText("film-002.png")).not.toBeInTheDocument();
    expect(screen.queryByText("film-003.png")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "无缺陷 (2)" }));

    expect(screen.queryByText("film-001.png")).not.toBeInTheDocument();
    expect(screen.getByText("film-002.png")).toBeInTheDocument();
    expect(screen.getByText("film-003.png")).toBeInTheDocument();
  });

  it("calls onBack and onReview when the corresponding buttons are clicked", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    const onReview = vi.fn();

    render(
      <ReportPreviewPage
        taskId="task-1"
        projectId="project-1"
        projectName="焊缝项目"
        onBack={onBack}
        onReview={onReview}
      />
    );

    await user.click((await screen.findByText("返回任务列表")).closest("button")!);
    await user.click(screen.getByText("查看审核详情").closest("button")!);

    expect(onBack).toHaveBeenCalledTimes(1);
    expect(onReview).toHaveBeenCalledTimes(1);
  });

  it("shows a fallback message when review callback is unavailable", async () => {
    const user = userEvent.setup();

    render(
      <ReportPreviewPage
        taskId="task-1"
        projectId="project-1"
        projectName="焊缝项目"
        onBack={vi.fn()}
      />
    );

    await user.click((await screen.findByText("查看审核详情")).closest("button")!);

    expect(messageMocks.info).toHaveBeenCalledWith("请通过报告列表进入审核");
  });
});
