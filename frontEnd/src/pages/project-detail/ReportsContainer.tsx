import React, { useState } from "react";
import ReportsPage from "./ReportsPage";
import ReportEditorPage from "./ReportEditorPage";
import ReportPreviewPage from "./ReportPreviewPage";

interface ReportsContainerProps {
  projectId: string;
  projectName?: string;
  permission?: string;
  projectSidebarCollapsed?: boolean;
  onProjectSidebarCollapseChange?: (collapsed: boolean) => void;
}

const ReportsContainer: React.FC<ReportsContainerProps> = ({
  projectId,
  projectName,
  permission,
  projectSidebarCollapsed,
  onProjectSidebarCollapseChange,
}) => {
  const [view, setView] = useState<"list" | "editor" | "preview">("list");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const handleReview = (taskId: string) => {
    setSelectedTaskId(taskId);
    setView("editor");
  };

  const handlePreview = (taskId: string) => {
    setSelectedTaskId(taskId);
    setView("preview");
  };

  const handleBack = () => {
    setView("list");
    setSelectedTaskId(null);
  };

  if (view === "editor" && selectedTaskId) {
    return (
      <ReportEditorPage
        taskId={selectedTaskId}
        projectId={projectId}
        projectName={projectName}
        onBack={handleBack}
        onPreview={() => setView("preview")}
        projectSidebarCollapsed={projectSidebarCollapsed}
        onProjectSidebarCollapseChange={onProjectSidebarCollapseChange}
      />
    );
  }

  if (view === "preview" && selectedTaskId) {
    return (
      <ReportPreviewPage
        taskId={selectedTaskId}
        projectId={projectId}
        projectName={projectName || "项目"}
        onBack={handleBack}
        onReview={() => setView("editor")}
      />
    );
  }

  return (
    <ReportsPage
      projectId={projectId}
      projectName={projectName}
      onReview={handleReview}
      onPreview={handlePreview}
    />
  );
};

export default ReportsContainer;

