import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach, describe, expect, it } from "vitest";
import ReportEditorPage from "./ReportEditorPage";
import type { TaskFile } from "../../utils/data";

const { reportApiMocks, refreshFilesMock, useRequestMock, messageMocks } = vi.hoisted(() => ({
  reportApiMocks: {
    getReportDetail: vi.fn(),
    getReportFiles: vi.fn(),
    batchConfirmFiles: vi.fn(),
  },
  refreshFilesMock: vi.fn(),
  useRequestMock: vi.fn(),
  messageMocks: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("../../utils/api", () => ({
  reportAPI: reportApiMocks,
}));

vi.mock("ahooks", () => ({
  useRequest: useRequestMock,
}));

vi.mock("./components/ImageEditorViewer", () => ({
  ImageEditorViewer: ({ file }: { file: TaskFile | null }) => (
    <div data-testid="image-editor-viewer">{file ? file.FileName : "empty"}</div>
  ),
}));

vi.mock("antd", () => {
  const Layout = ({ children, ...props }: any) => <div {...props}>{children}</div>;
  Layout.Content = React.forwardRef<HTMLDivElement, any>(({ children, ...props }, ref) => (
    <div ref={ref} {...props}>
      {children}
    </div>
  ));
  Layout.Sider = ({ children, theme: _theme, width: _width, ...props }: any) => (
    <aside {...props}>{children}</aside>
  );

  const List = ({ dataSource = [], renderItem, loading }: any) => (
    <div data-loading={loading ? "true" : "false"}>
      {dataSource.map((item: any, index: number) => (
        <React.Fragment key={item.TaskFileId ?? index}>{renderItem(item)}</React.Fragment>
      ))}
    </div>
  );
  List.Item = ({ children, onClick, style }: any) => (
    <div role="listitem" onClick={onClick} style={style}>
      {children}
    </div>
  );

  const Typography = {
    Title: ({ children, level: _level, ...props }: any) => <h4 {...props}>{children}</h4>,
    Text: ({ children, strong: _strong, ellipsis: _ellipsis, ...props }: any) => (
      <span {...props}>{children}</span>
    ),
  };

  const Space = ({ children, ...props }: any) => <div {...props}>{children}</div>;

  const Button = ({
    children,
    icon,
    onClick,
    type: _buttonType,
    size: _size,
    block: _block,
    danger: _danger,
    ...props
  }: any) => (
    <button type="button" onClick={onClick} {...props}>
      {icon}
      {children}
    </button>
  );

  const Checkbox = ({
    children,
    checked,
    onChange,
    onClick,
    indeterminate: _indeterminate,
    ...props
  }: any) => (
    <label>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange?.(event)}
        onClick={onClick}
        {...props}
      />
      {children}
    </label>
  );

  const Select = ({ value, onChange, options = [], placement: _placement, ...props }: any) => (
    <select value={value} onChange={(event) => onChange?.(Number(event.target.value))} {...props}>
      {options.map((option: any) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );

  const Progress = ({ percent }: any) => <div>{percent}%</div>;
  const Tooltip = ({ children }: any) => <>{children}</>;
  const Pagination = ({ current, total, pageSize, simple: _simple, showSizeChanger: _showSizeChanger, size: _size, ...props }: any) => (
    <div {...props}>{`page:${current}/${Math.max(1, Math.ceil(total / pageSize))}`}</div>
  );
  const Switch = ({ checked, onChange }: any) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange?.(!checked)}
    />
  );

  return {
    Layout,
    List,
    Typography,
    Space,
    Button,
    Select,
    Checkbox,
    Progress,
    Tooltip,
    Pagination,
    Switch,
    message: messageMocks,
  };
});

const buildFile = (index: number, overrides: Partial<TaskFile> = {}): TaskFile => ({
  TaskFileId: `task-file-${index}`,
  FileId: `file-${index}`,
  FileName: `image-${index}.png`,
  Status: "completed",
  ReviewStatus: index === 1 ? "CONFIRMED" : "PENDING",
  ...overrides,
});

const reportDetailResponse = {
  Code: 200,
  Message: "ok",
  Data: {
    ReportId: "report-1",
    TaskId: "task-1",
    ProjectId: "project-1",
    UserId: "user-1",
    ReportName: "焊缝评片报告",
    TotalFiles: 3,
    ConfirmedFiles: 1,
    TotalDefects: 0,
    SevereDefects: 0,
    NormalDefects: 0,
    Status: "PENDING" as const,
    CreatedAt: "2026-04-26T00:00:00Z",
    UpdatedAt: "2026-04-26T00:00:00Z",
  },
};

const renderPage = () =>
  render(
    <ReportEditorPage
      taskId="task-123456"
      projectId="project-123"
      onBack={vi.fn()}
      onPreview={vi.fn()}
      onProjectSidebarCollapseChange={vi.fn()}
    />
  );

describe("ReportEditorPage", () => {
  beforeEach(() => {
    const files = [buildFile(1), buildFile(2), buildFile(3)];

    refreshFilesMock.mockReset();
    useRequestMock.mockReset();
    reportApiMocks.getReportDetail.mockResolvedValue(reportDetailResponse);
    reportApiMocks.getReportFiles.mockResolvedValue({
      Code: 200,
      Message: "ok",
      Data: files,
    });
    reportApiMocks.batchConfirmFiles.mockResolvedValue({
      Code: 200,
      Message: "ok",
      Data: null,
    });

    useRequestMock.mockImplementation((service: () => unknown) => {
      const source = service.toString();

      if (source.includes("getReportDetail")) {
        return { data: reportDetailResponse };
      }

      if (source.includes("getReportFiles")) {
        return {
          data: {
            Code: 200,
            Message: "ok",
            Data: files,
          },
          loading: false,
          refresh: refreshFilesMock,
        };
      }

      return {};
    });
  });

  it("loads report data and auto-selects the first file", async () => {
    renderPage();

    expect(await screen.findByText("焊缝评片报告")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("image-editor-viewer")).toHaveTextContent("image-1.png");
    });

    expect(screen.getByText("文件总数: 3个")).toBeInTheDocument();
    expect(screen.getAllByText("33%")).toHaveLength(2);
  });

  it("updates the active file in single mode when a new file is clicked", async () => {
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("image-2.png");

    await user.click(screen.getByText("image-2.png"));

    await waitFor(() => {
      expect(screen.getByTestId("image-editor-viewer")).toHaveTextContent("image-2.png");
    });
  });

  it("batch confirms selected files and refreshes the file list", async () => {
    const user = userEvent.setup();

    renderPage();
    const selectAll = await screen.findByRole("checkbox", { name: "全选" });

    await user.click(selectAll);
    await user.click(screen.getByRole("button", { name: "批量确认 (3)" }));

    await waitFor(() => {
      expect(reportApiMocks.batchConfirmFiles).toHaveBeenCalledWith([
        "task-file-1",
        "task-file-2",
        "task-file-3",
      ]);
    });

    expect(messageMocks.success).toHaveBeenCalledWith("成功批量确认 3 个文件");
    expect(refreshFilesMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "批量确认 (3)" })).not.toBeInTheDocument();
  });

  it("switches to compare mode and places the next clicked file into the second pane", async () => {
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("image-2.png");

    await user.click(screen.getByRole("switch"));

    await waitFor(() => {
      expect(screen.getAllByTestId("image-editor-viewer")).toHaveLength(1);
    });
    expect(screen.getByText("请在左侧选择图片 2")).toBeInTheDocument();

    await user.click(screen.getByText("image-2.png"));

    await waitFor(() => {
      const viewers = screen.getAllByTestId("image-editor-viewer");
      expect(viewers).toHaveLength(2);
      expect(viewers[0]).toHaveTextContent("image-1.png");
      expect(viewers[1]).toHaveTextContent("image-2.png");
    });
  });

  it("resets compare mode to a new first pane when a third file is clicked", async () => {
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("image-3.png");

    await user.click(screen.getByRole("switch"));
    await user.click(screen.getByText("image-2.png"));

    await waitFor(() => {
      const viewers = screen.getAllByTestId("image-editor-viewer");
      expect(viewers).toHaveLength(2);
      expect(viewers[0]).toHaveTextContent("image-1.png");
      expect(viewers[1]).toHaveTextContent("image-2.png");
    });

    await user.click(screen.getByText("image-3.png"));

    await waitFor(() => {
      expect(screen.getByText("请在左侧选择图片 2")).toBeInTheDocument();
      const viewers = screen.getAllByTestId("image-editor-viewer");
      expect(viewers).toHaveLength(1);
      expect(viewers[0]).toHaveTextContent("image-3.png");
    });
  });
});
