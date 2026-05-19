import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ReportsContainer from "./ReportsContainer";

vi.mock("./ReportsPage", () => ({
  default: ({
    projectId,
    projectName,
    onReview,
    onPreview,
  }: {
    projectId: string;
    projectName?: string;
    onReview: (taskId: string) => void;
    onPreview: (taskId: string) => void;
  }) => (
    <div>
      <div>{`reports-list:${projectId}:${projectName}`}</div>
      <button type="button" onClick={() => onReview("task-review")}>
        进入评片
      </button>
      <button type="button" onClick={() => onPreview("task-preview")}>
        进入预览
      </button>
    </div>
  ),
}));

vi.mock("./ReportEditorPage", () => ({
  default: ({
    taskId,
    projectId,
    projectName,
    onBack,
    onPreview,
  }: {
    taskId: string;
    projectId: string;
    projectName?: string;
    onBack: () => void;
    onPreview?: () => void;
  }) => (
    <div>
      <div>{`editor:${taskId}:${projectId}:${projectName}`}</div>
      <button type="button" onClick={onBack}>
        返回列表
      </button>
      <button type="button" onClick={onPreview}>
        去预览
      </button>
    </div>
  ),
}));

vi.mock("./ReportPreviewPage", () => ({
  default: ({
    taskId,
    projectId,
    projectName,
    onBack,
    onReview,
  }: {
    taskId: string;
    projectId: string;
    projectName: string;
    onBack: () => void;
    onReview: () => void;
  }) => (
    <div>
      <div>{`preview:${taskId}:${projectId}:${projectName}`}</div>
      <button type="button" onClick={onBack}>
        返回列表
      </button>
      <button type="button" onClick={onReview}>
        去评片
      </button>
    </div>
  ),
}));

const renderContainer = (
  ui: ReactElement,
  initialEntries = ["/projects/project-1/reports"]
) => render(<MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>);

describe("ReportsContainer", () => {
  it("switches from report list to editor and back", async () => {
    const user = userEvent.setup();

    renderContainer(<ReportsContainer projectId="project-1" projectName="焊缝项目" />);

    expect(screen.getByText("reports-list:project-1:焊缝项目")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "进入评片" }));

    expect(screen.getByText("editor:task-review:project-1:焊缝项目")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回列表" }));

    expect(screen.getByText("reports-list:project-1:焊缝项目")).toBeInTheDocument();
  });

  it("switches between editor and preview while keeping the selected task", async () => {
    const user = userEvent.setup();

    renderContainer(<ReportsContainer projectId="project-1" projectName="焊缝项目" />);

    await user.click(screen.getByRole("button", { name: "进入评片" }));
    await user.click(screen.getByRole("button", { name: "去预览" }));

    expect(screen.getByText("preview:task-review:project-1:焊缝项目")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "去评片" }));

    expect(screen.getByText("editor:task-review:project-1:焊缝项目")).toBeInTheDocument();
  });

  it("opens preview directly from the list with the clicked task id", async () => {
    const user = userEvent.setup();

    renderContainer(<ReportsContainer projectId="project-1" />);

    await user.click(screen.getByRole("button", { name: "进入预览" }));

    expect(screen.getByText("preview:task-preview:project-1:项目")).toBeInTheDocument();
  });

  it("opens the editor directly from a report review query", () => {
    renderContainer(
      <ReportsContainer projectId="project-1" projectName="焊缝项目" />,
      ["/projects/project-1/reports?taskId=task-direct&view=review"]
    );

    expect(screen.getByText("editor:task-direct:project-1:焊缝项目")).toBeInTheDocument();
  });
});
