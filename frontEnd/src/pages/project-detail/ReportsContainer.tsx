import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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

type ReportsContainerView = "list" | "editor" | "preview";

const getViewFromRoute = (
  taskId: string | null,
  viewParam: string | null
): ReportsContainerView => {
  if (!taskId) {
    return "list";
  }

  return viewParam === "preview" ? "preview" : "editor";
};

const ReportsContainer: React.FC<ReportsContainerProps> = ({
  projectId,
  projectName,
  permission,
  projectSidebarCollapsed,
  onProjectSidebarCollapseChange,
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const routeTaskId = searchParams.get("taskId");
  const routeView = searchParams.get("view");

  const [view, setView] = useState<ReportsContainerView>(() =>
    getViewFromRoute(routeTaskId, routeView)
  );
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(() => routeTaskId);

  useEffect(() => {
    setSelectedTaskId(routeTaskId);
    setView(getViewFromRoute(routeTaskId, routeView));
  }, [routeTaskId, routeView]);

  const setRouteView = (nextView: Exclude<ReportsContainerView, "list">, taskId: string) => {
    setSearchParams({
      taskId,
      view: nextView === "editor" ? "review" : "preview",
    });
  };

  const handleReview = (taskId: string) => {
    setSelectedTaskId(taskId);
    setView("editor");
    setRouteView("editor", taskId);
  };

  const handlePreview = (taskId: string) => {
    setSelectedTaskId(taskId);
    setView("preview");
    setRouteView("preview", taskId);
  };

  const handleBack = () => {
    setView("list");
    setSelectedTaskId(null);
    setSearchParams({});
  };

  if (view === "editor" && selectedTaskId) {
    return (
      <ReportEditorPage
        taskId={selectedTaskId}
        projectId={projectId}
        projectName={projectName}
        onBack={handleBack}
        onPreview={() => selectedTaskId && handlePreview(selectedTaskId)}
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
        onReview={() => selectedTaskId && handleReview(selectedTaskId)}
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
