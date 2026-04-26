import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useReportEditorState } from "./useReportEditorState";
import type { TaskFile } from "../../../utils/data";

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

vi.mock("ahooks", () => ({
  useRequest: useRequestMock,
}));

vi.mock("antd", () => ({
  message: messageMocks,
}));

vi.mock("../../../utils/api", () => ({
  reportAPI: reportApiMocks,
}));

const buildFile = (index: number, overrides: Partial<TaskFile> = {}): TaskFile => ({
  TaskFileId: `task-file-${index}`,
  FileId: `file-${index}`,
  FileName: `image-${index}.png`,
  Status: "completed",
  ReviewStatus: index === 1 ? "CONFIRMED" : "PENDING",
  ...overrides,
});

describe("useReportEditorState", () => {
  let files: TaskFile[];

  beforeEach(() => {
    files = [buildFile(1), buildFile(2), buildFile(3)];

    refreshFilesMock.mockReset();
    useRequestMock.mockReset();
    messageMocks.success.mockReset();
    messageMocks.warning.mockReset();
    messageMocks.error.mockReset();
    reportApiMocks.batchConfirmFiles.mockReset();

    useRequestMock.mockImplementation((service: () => unknown) => {
      const source = service.toString();

      if (source.includes("getReportDetail")) {
        return {
          data: {
            Code: 200,
            Message: "ok",
            Data: {
              ReportId: "report-1",
              TaskId: "task-1",
              ProjectId: "project-1",
              UserId: "user-1",
              ReportName: "焊缝评片报告",
              TotalFiles: files.length,
              ConfirmedFiles: 1,
              TotalDefects: 0,
              SevereDefects: 0,
              NormalDefects: 0,
              Status: "PENDING" as const,
              CreatedAt: "2026-04-26T00:00:00Z",
              UpdatedAt: "2026-04-26T00:00:00Z",
            },
          },
        };
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

  it("auto-selects the first file and computes progress stats", async () => {
    const { result } = renderHook(() => useReportEditorState({ taskId: "task-1" }));

    await waitFor(() => {
      expect(result.current.selectedFile?.TaskFileId).toBe("task-file-1");
    });

    expect(result.current.confirmedCount).toBe(1);
    expect(result.current.unconfirmedCount).toBe(2);
    expect(result.current.progressPercent).toBe(33);
    expect(result.current.paginatedFiles).toHaveLength(3);
  });

  it("seeds compare mode from the selected file and fills the second compare slot", async () => {
    const { result } = renderHook(() => useReportEditorState({ taskId: "task-1" }));

    await waitFor(() => {
      expect(result.current.selectedFile?.TaskFileId).toBe("task-file-1");
    });

    act(() => {
      result.current.setViewMode("compare");
    });

    expect(result.current.compareSelectedFiles[0]?.TaskFileId).toBe("task-file-1");
    expect(result.current.compareSelectedFiles[1]).toBeNull();

    act(() => {
      result.current.selectFileForCurrentMode(files[1]);
    });

    expect(result.current.compareSelectedFiles[0]?.TaskFileId).toBe("task-file-1");
    expect(result.current.compareSelectedFiles[1]?.TaskFileId).toBe("task-file-2");
  });

  it("resets compare selection when choosing a new file after both slots are filled", async () => {
    const { result } = renderHook(() => useReportEditorState({ taskId: "task-1" }));

    await waitFor(() => {
      expect(result.current.selectedFile?.TaskFileId).toBe("task-file-1");
    });

    act(() => {
      result.current.setViewMode("compare");
    });

    act(() => {
      result.current.selectFileForCurrentMode(files[1]);
    });

    expect(result.current.compareSelectedFiles[0]?.TaskFileId).toBe("task-file-1");
    expect(result.current.compareSelectedFiles[1]?.TaskFileId).toBe("task-file-2");

    act(() => {
      result.current.selectFileForCurrentMode(files[2]);
    });

    expect(result.current.compareSelectedFiles[0]?.TaskFileId).toBe("task-file-3");
    expect(result.current.compareSelectedFiles[1]).toBeNull();
  });

  it("warns when batch confirm is triggered without any selected file", async () => {
    const { result } = renderHook(() => useReportEditorState({ taskId: "task-1" }));

    await act(async () => {
      await result.current.handleBatchConfirm();
    });

    expect(messageMocks.warning).toHaveBeenCalledWith("请先选择要确认的文件");
    expect(reportApiMocks.batchConfirmFiles).not.toHaveBeenCalled();
  });

  it("confirms selected files, clears selection, and refreshes the list", async () => {
    reportApiMocks.batchConfirmFiles.mockResolvedValue({
      Code: 200,
      Message: "ok",
      Data: null,
    });

    const { result } = renderHook(() => useReportEditorState({ taskId: "task-1" }));

    act(() => {
      result.current.handleSelectOne("task-file-1", true);
      result.current.handleSelectOne("task-file-2", true);
    });

    await act(async () => {
      await result.current.handleBatchConfirm();
    });

    expect(reportApiMocks.batchConfirmFiles).toHaveBeenCalledWith([
      "task-file-1",
      "task-file-2",
    ]);
    expect(messageMocks.success).toHaveBeenCalledWith("成功批量确认 2 个文件");
    expect(result.current.selectedIds.size).toBe(0);
    expect(refreshFilesMock).toHaveBeenCalledTimes(1);
  });

  it("drops stale selections when the file list changes", async () => {
    const { result, rerender } = renderHook(() =>
      useReportEditorState({ taskId: "task-1" })
    );

    await waitFor(() => {
      expect(result.current.selectedFile?.TaskFileId).toBe("task-file-1");
    });

    act(() => {
      result.current.handleSelectOne("task-file-1", true);
      result.current.handleSelectOne("task-file-2", true);
      result.current.setViewMode("compare");
      result.current.selectFileForCurrentMode(files[1]);
    });

    files = [buildFile(3)];
    rerender();

    await waitFor(() => {
      expect(result.current.selectedFile?.TaskFileId).toBe("task-file-3");
    });

    expect(Array.from(result.current.selectedIds)).toEqual([]);
    expect(result.current.compareSelectedFiles).toEqual([null, null]);
  });
});
