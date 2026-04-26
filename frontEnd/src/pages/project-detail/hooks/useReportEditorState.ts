import { useEffect, useMemo, useState } from "react";
import { message } from "antd";
import { useRequest } from "ahooks";
import { reportAPI } from "../../../utils/api";
import type { Report, TaskFile } from "../../../utils/data";

export type ReportEditorViewMode = "single" | "compare";

interface UseReportEditorStateParams {
  taskId: string;
}

interface UseReportEditorStateResult {
  report: Report | undefined;
  files: TaskFile[];
  filesLoading: boolean;
  refreshFiles: () => void;
  selectedFile: TaskFile | null;
  viewMode: ReportEditorViewMode;
  compareSelectedFiles: [TaskFile | null, TaskFile | null];
  selectedIds: Set<string>;
  currentPage: number;
  pageSize: number;
  confirmedCount: number;
  unconfirmedCount: number;
  progressPercent: number;
  paginatedFiles: TaskFile[];
  setCurrentPage: (page: number) => void;
  setPageSizeAndReset: (size: number) => void;
  setSelectedFile: (file: TaskFile | null) => void;
  setViewMode: (mode: ReportEditorViewMode) => void;
  selectFileForCurrentMode: (file: TaskFile) => void;
  handleSelectAll: (checked: boolean) => void;
  handleSelectOne: (id: string, checked: boolean) => void;
  handleBatchConfirm: () => Promise<void>;
}

export function useReportEditorState({
  taskId,
}: UseReportEditorStateParams): UseReportEditorStateResult {
  const [selectedFile, setSelectedFile] = useState<TaskFile | null>(null);
  const [viewMode, setViewModeState] = useState<ReportEditorViewMode>("single");
  const [compareSelectedFiles, setCompareSelectedFiles] = useState<
    [TaskFile | null, TaskFile | null]
  >([null, null]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { data: reportResp } = useRequest(() => reportAPI.getReportDetail(taskId));
  const report = reportResp?.Data;

  const {
    data: filesResp,
    loading: filesLoading,
    refresh: refreshFiles,
  } = useRequest(() => reportAPI.getReportFiles(taskId));
  const files: TaskFile[] = filesResp?.Data || [];

  const confirmedCount = files.filter((file) => file.ReviewStatus === "CONFIRMED").length;
  const unconfirmedCount = files.length - confirmedCount;
  const progressPercent =
    files.length > 0 ? Math.round((confirmedCount / files.length) * 100) : 0;

  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return files.slice(start, start + pageSize);
  }, [files, currentPage, pageSize]);

  useEffect(() => {
    if (!files.length) {
      setSelectedFile(null);
      setSelectedIds(new Set());
      return;
    }

    setSelectedFile((currentSelectedFile) => {
      if (!currentSelectedFile) {
        return files[0];
      }

      const nextSelectedFile =
        files.find((file) => file.TaskFileId === currentSelectedFile.TaskFileId) || files[0];
      return nextSelectedFile;
    });

    setSelectedIds((currentSelectedIds) => {
      const nextSelectedIds = new Set(
        Array.from(currentSelectedIds).filter((id) =>
          files.some((file) => file.TaskFileId === id)
        )
      );

      if (nextSelectedIds.size === currentSelectedIds.size) {
        return currentSelectedIds;
      }

      return nextSelectedIds;
    });
  }, [files]);

  useEffect(() => {
    setCompareSelectedFiles(([left, right]) => {
      const nextLeft =
        left && files.some((file) => file.TaskFileId === left.TaskFileId) ? left : null;
      const nextRight =
        right && files.some((file) => file.TaskFileId === right.TaskFileId) ? right : null;

      if (nextLeft === left && nextRight === right) {
        return [left, right];
      }

      return [nextLeft, nextRight];
    });
  }, [files]);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(files.map((file) => file.TaskFileId)));
      return;
    }

    setSelectedIds(new Set());
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    setSelectedIds((currentSelectedIds) => {
      const nextSelectedIds = new Set(currentSelectedIds);

      if (checked) {
        nextSelectedIds.add(id);
      } else {
        nextSelectedIds.delete(id);
      }

      return nextSelectedIds;
    });
  };

  const setViewMode = (mode: ReportEditorViewMode) => {
    setViewModeState(mode);

    if (mode === "compare" && selectedFile) {
      setCompareSelectedFiles([selectedFile, null]);
    }
  };

  const selectFileForCurrentMode = (file: TaskFile) => {
    if (viewMode === "single") {
      setSelectedFile(file);
      return;
    }

    setCompareSelectedFiles((currentCompareSelectedFiles) => {
      const [left, right] = currentCompareSelectedFiles;

      if (!left || right) {
        return [file, null];
      }

      return [left, file];
    });
  };

  const handleBatchConfirm = async () => {
    if (selectedIds.size === 0) {
      message.warning("请先选择要确认的文件");
      return;
    }

    try {
      await reportAPI.batchConfirmFiles(Array.from(selectedIds));
      message.success(`成功批量确认 ${selectedIds.size} 个文件`);
      setSelectedIds(new Set());
      refreshFiles();
    } catch (error) {
      console.error(error);
    }
  };

  const setPageSizeAndReset = (size: number) => {
    setPageSize(size);
    setCurrentPage(1);
  };

  return {
    report,
    files,
    filesLoading,
    refreshFiles,
    selectedFile,
    viewMode,
    compareSelectedFiles,
    selectedIds,
    currentPage,
    pageSize,
    confirmedCount,
    unconfirmedCount,
    progressPercent,
    paginatedFiles,
    setCurrentPage,
    setPageSizeAndReset,
    setSelectedFile,
    setViewMode,
    selectFileForCurrentMode,
    handleSelectAll,
    handleSelectOne,
    handleBatchConfirm,
  };
}
