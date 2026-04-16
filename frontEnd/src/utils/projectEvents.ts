export const PROJECTS_UPDATED_EVENT = "projects-updated";

export const notifyProjectsUpdated = () => {
  window.dispatchEvent(new Event(PROJECTS_UPDATED_EVENT));
};
