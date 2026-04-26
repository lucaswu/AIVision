import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportsPage from "./ReportsPage";
import type { Report } from "../../utils/data";

const { reportApiMocks, useRequestMock, navigateMock, messageMocks } = vi.hoisted(() => ({
  reportApiMocks: {
    getReports: vi.fn(),
    archiveReport: vi.fn(),
    downloadReport: vi.fn(),
  },
  useRequestMock: vi.fn(),
  navigateMock: vi.fn(),
  messageMocks: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("ahooks", () => ({
  useRequest: useRequestMock,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");

  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../../utils/api", () => ({
  reportAPI: reportApiMocks,
}));

vi.mock("antd", () => {
  const Space = ({ children, ...props }: any) => <div {...props}>{children}</div>;
  const Card = ({ children, title, extra }: any) => (
    <section>
      {title ? <div>{title}</div> : null}
      {extra ? <div>{extra}</div> : null}
      <div>{children}</div>
    </section>
  );
  const Breadcrumb = ({ items }: any) => (
    <nav>{items.map((item: any) => item.title).join(" / ")}</nav>
  );
  const Row = ({ children }: any) => <div>{children}</div>;
  const Col = ({ children }: any) => <div>{children}</div>;
  const Statistic = ({ title, value }: any) => (
    <div>{`${title}:${value}`}</div>
  );
  const Tooltip = ({ title, children }: any) =>
    React.isValidElement(children)
      ? React.cloneElement(children as React.ReactElement<any>, { "aria-label": title })
      : children;
  const Button = ({
    children,
    icon,
    onClick,
    type: _buttonType,
    disabled,
    ...props
  }: any) => (
    <button type="button" onClick={onClick} disabled={disabled} {...props}>
      {icon}
      {children}
    </button>
  );
  const Typography = {
    Title: ({ children }: any) => <h2>{children}</h2>,
    Text: ({ children }: any) => <span>{children}</span>,
    Link: ({ children, onClick }: any) => (
      <button type="button" onClick={onClick}>
        {children}
      </button>
    ),
  };
  const Tag = ({ children }: any) => <span>{children}</span>;
  const Table = ({
    columns,
    dataSource,
    loading,
    pagination,
    rowKey,
  }: any) => (
    <div>
      <div>{loading ? "loading" : "ready"}</div>
      {dataSource.map((record: any) => (
        <div key={record[rowKey]}>
          {columns.map((column: any) => {
            const value = column.dataIndex ? record[column.dataIndex] : undefined;
            const content = column.render
              ? column.render(value, record)
              : value;
            return (
              <div key={column.key ?? column.dataIndex}>
                {content}
              </div>
            );
          })}
        </div>
      ))}
      <button type="button" onClick={() => pagination.onChange(2, 20)}>
        翻页
      </button>
      <div>{pagination.showTotal(dataSource.length)}</div>
    </div>
  );

  return {
    Card,
    Table,
    Space,
    Typography,
    Tag,
    Button,
    message: messageMocks,
    Breadcrumb,
    Tooltip,
    Statistic,
    Row,
    Col,
  };
});

const buildReport = (overrides: Partial<Report> = {}): Report => ({
  ReportId: "report-1",
  TaskId: "task-1",
  TaskName: "焊缝检测任务",
  ProjectId: "project-1",
  UserId: "user-1",
  ReportName: "焊缝报告",
  TotalFiles: 12,
  ConfirmedFiles: 6,
  TotalDefects: 3,
  SevereDefects: 1,
  NormalDefects: 2,
  Status: "PENDING",
  CreatedAt: "2026-04-26 10:00:00",
  UpdatedAt: "2026-04-26 10:00:00",
  ...overrides,
});

describe("ReportsPage", () => {
  beforeEach(() => {
    const reports = [
      buildReport(),
      buildReport({
        ReportId: "report-2",
        TaskId: "task-2",
        ReportName: "已归档报告",
        Status: "ARCHIVED",
        SevereDefects: 0,
        NormalDefects: 0,
      }),
    ];

    reportApiMocks.getReports.mockResolvedValue({
      Code: 200,
      Message: "ok",
      Data: reports,
    });
    reportApiMocks.archiveReport.mockResolvedValue({
      Code: 200,
      Message: "ok",
      Data: null,
    });
    reportApiMocks.downloadReport.mockImplementation(
      (reportId: string) => `/download/${reportId}`
    );

    useRequestMock.mockReset();
    useRequestMock.mockImplementation((service: () => unknown) => {
      const source = service.toString();

      if (source.includes("getReports")) {
        return {
          data: {
            Code: 200,
            Message: "ok",
            Data: reports,
          },
          loading: false,
          refresh: vi.fn(),
        };
      }

      return {};
    });

    navigateMock.mockReset();
    messageMocks.success.mockReset();
  });

  it("renders report stats and triggers preview/review callbacks", async () => {
    const onReview = vi.fn();
    const onPreview = vi.fn();
    const user = userEvent.setup();

    render(
      <ReportsPage
        projectId="project-1"
        projectName="焊缝项目"
        onReview={onReview}
        onPreview={onPreview}
      />
    );

    expect(screen.getByText("总报告数:2")).toBeInTheDocument();
    expect(screen.getByText("待审核:1")).toBeInTheDocument();
    expect(screen.getByText("已归档:1")).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "查看" })[0]);
    await user.click(screen.getAllByRole("button", { name: "审核" })[0]);

    expect(onPreview).toHaveBeenCalledWith("task-1");
    expect(onReview).toHaveBeenCalledWith("task-1");
  });

  it("archives a report and refreshes the list", async () => {
    const refreshMock = vi.fn();
    const user = userEvent.setup();

    useRequestMock.mockImplementation(() => ({
      data: {
        Code: 200,
        Message: "ok",
        Data: [buildReport()],
      },
      loading: false,
      refresh: refreshMock,
    }));

    render(
      <ReportsPage
        projectId="project-1"
        onReview={vi.fn()}
        onPreview={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: "归档" }));

    await waitFor(() => {
      expect(reportApiMocks.archiveReport).toHaveBeenCalledWith("report-1", true);
    });
    expect(messageMocks.success).toHaveBeenCalledWith("报告已归档");
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("downloads a report by creating and clicking a temporary link", async () => {
    const user = userEvent.setup();
    const appendChildSpy = vi.spyOn(document.body, "appendChild");
    const removeChildSpy = vi.spyOn(document.body, "removeChild");
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    render(
      <ReportsPage
        projectId="project-1"
        onReview={vi.fn()}
        onPreview={vi.fn()}
      />
    );

    await user.click(screen.getAllByRole("button", { name: "下载" })[0]);

    expect(reportApiMocks.downloadReport).toHaveBeenCalledWith("report-1");
    expect(appendChildSpy).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(removeChildSpy).toHaveBeenCalled();
  });

  it("navigates to the task page when the task link is clicked", async () => {
    const user = userEvent.setup();

    render(
      <ReportsPage
        projectId="project-1"
        onReview={vi.fn()}
        onPreview={vi.fn()}
      />
    );

    await user.click(screen.getAllByRole("button", { name: "焊缝检测任务" })[0]);

    expect(navigateMock).toHaveBeenCalledWith("/projects/project-1/tasks");
  });
});
