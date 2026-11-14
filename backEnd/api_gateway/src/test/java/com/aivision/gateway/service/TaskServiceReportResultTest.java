package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * 第三方报告对接：GET /api/v1/tasks/{task_id}/report-result 与任务列表 scope 参数
 */
@ExtendWith(MockitoExtension.class)
class TaskServiceReportResultTest {

    @Mock private TaskRepository taskRepository;
    @Mock private TaskFileRepository taskFileRepository;
    @Mock private WeldJointRepository weldJointRepository;
    @Mock private FileRepository fileRepository;
    @Mock private DirectoryRepository directoryRepository;
    @Mock private ProjectRepository projectRepository;
    @Mock private UserProjectPermissionRepository permissionRepository;
    @Mock private UserRepository userRepository;
    @Mock private TaskProcessService taskProcessService;

    @InjectMocks
    private TaskService taskService;

    private final String projectId = "proj-1";
    private final String ownerId = "owner";
    private final String taskId = "task-1";

    @BeforeEach
    void setUp() {
        Project project = new Project();
        project.setProjectId(projectId);
        project.setProjectName("某管线项目");
        project.setOwnerId(ownerId);
        lenient().when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        lenient().when(userRepository.findById(anyString())).thenReturn(Optional.empty());
        lenient().when(permissionRepository.findByUserIdAndProjectId(anyString(), anyString()))
            .thenReturn(Optional.empty());
    }

    private Task newTask(String projectIdOfTask) {
        Task task = new Task();
        task.setTaskId(taskId);
        task.setTaskName("检测任务A");
        task.setProjectId(projectIdOfTask);
        task.setUserId(ownerId);
        task.setStatus(Task.Status.COMPLETED);
        task.setCreatedAt(LocalDateTime.of(2026, 11, 1, 10, 0, 0));
        task.setUpdatedAt(LocalDateTime.of(2026, 11, 1, 10, 5, 0));
        task.setEndTime(LocalDateTime.of(2026, 11, 1, 10, 5, 0));
        return task;
    }

    private TaskFile newTaskFile(String taskFileId, String fileId) {
        TaskFile tf = new TaskFile();
        tf.setTaskFileId(taskFileId);
        tf.setTaskId(taskId);
        tf.setFileId(fileId);
        tf.setStatus(TaskFile.Status.COMPLETED);
        tf.setFilmNumber("3-4");
        return tf;
    }

    private DefectRecord defect(String id, String taskFileId, String weldJointId, String position, String geometry) {
        DefectRecord dr = new DefectRecord(id, taskFileId, "气孔", position, "3.5mm", "I", "");
        dr.setWeldJointId(weldJointId);
        dr.setGeometry(geometry);
        return dr;
    }

    private File file(String fileId, String name) {
        File f = new File();
        f.setFileId(fileId);
        f.setOriginalName(name);
        return f;
    }

    @Test
    void reportResult_expandsByWeldJointAndKeepsUnassignedDefects() {
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(newTask(projectId)));

        TaskFile tf = newTaskFile("tf-1", "file-1");
        WeldJoint j1 = new WeldJoint("wj-1", "tf-1", "HJ-001", 0);
        WeldJoint j2 = new WeldJoint("wj-2", "tf-1", "HJ-002", 1);
        tf.setWeldJoints(new ArrayList<>(Arrays.asList(j1, j2)));
        tf.setDefectRecords(new ArrayList<>(Arrays.asList(
            defect("d1", "tf-1", "wj-1", null, "{\"type\":\"rect\",\"x\":100,\"y\":280,\"w\":40,\"h\":40}"),
            defect("d2", "tf-1", "wj-2", "距焊口起点 120mm", null),
            defect("d3", "tf-1", null, null, null)
        )));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(Collections.singletonList(tf));
        when(fileRepository.findByFileIdIn(anyList())).thenReturn(Collections.singletonList(file("file-1", "A14.bmp")));

        TaskReportResultResponse resp = taskService.getTaskReportResultByTask(taskId, projectId, ownerId);

        assertEquals(taskId, resp.getTaskId());
        assertEquals("检测任务A", resp.getTaskName());
        assertEquals("某管线项目", resp.getProjectName());
        assertEquals("completed", resp.getStatus());
        assertEquals("2026-11-01 10:00:00", resp.getCreateTime());
        // 2 个焊口 + 1 条未分组
        assertEquals(3, resp.getTotal());
        List<ReportResultResponse.ReportItem> items = resp.getReportItems();

        assertEquals("HJ-001", items.get(0).getWeldNo());
        assertEquals("A14.bmp", items.get(0).getFileName());
        assertEquals("3-4", items.get(0).getSliceNo());
        assertEquals(1, items.get(0).getDefects().size());
        ReportResultResponse.DefectItem d1 = items.get(0).getDefects().get(0);
        assertEquals("X:120, Y:300", d1.getDefectLocation());
        assertEquals(Arrays.asList(100.0, 280.0, 140.0, 320.0), d1.getDefectBBox());

        assertEquals("HJ-002", items.get(1).getWeldNo());
        ReportResultResponse.DefectItem d2 = items.get(1).getDefects().get(0);
        assertEquals("距焊口起点 120mm", d2.getDefectLocation(), "人工填写的位置优先");
        assertNull(d2.getDefectBBox());

        assertNull(items.get(2).getWeldNo());
        assertEquals("d3", items.get(2).getDefects().get(0).getDefectId());

        // 文件名批量查询，不逐条查询
        verify(fileRepository, never()).findById(anyString());
    }

    @Test
    void reportResult_filmWithoutWeldJointsReturnsSingleItemWithAllDefects() {
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(newTask(projectId)));
        TaskFile tf = newTaskFile("tf-1", "file-1");
        tf.setDefectRecords(new ArrayList<>(Arrays.asList(
            defect("d1", "tf-1", null, null, "[10, 20, 30, 40]"),
            defect("d2", "tf-1", null, null, null)
        )));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(Collections.singletonList(tf));
        when(fileRepository.findByFileIdIn(anyList())).thenReturn(Collections.emptyList());

        TaskReportResultResponse resp = taskService.getTaskReportResultByTask(taskId, projectId, ownerId);

        assertEquals(1, resp.getTotal());
        ReportResultResponse.ReportItem item = resp.getReportItems().get(0);
        assertEquals("unknown", item.getFileName());
        assertEquals(2, item.getDefects().size());
        assertEquals("X:20, Y:30", item.getDefects().get(0).getDefectLocation());
    }

    @Test
    void reportResult_taskNotFound() {
        when(taskRepository.findById(taskId)).thenReturn(Optional.empty());
        assertThrows(NoSuchElementException.class,
            () -> taskService.getTaskReportResultByTask(taskId, projectId, ownerId));
    }

    @Test
    void reportResult_taskInOtherProjectTreatedAsNotFound() {
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(newTask("other-project")));
        assertThrows(NoSuchElementException.class,
            () -> taskService.getTaskReportResultByTask(taskId, projectId, ownerId));
    }

    @Test
    void reportResult_noProjectPermission() {
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(newTask(projectId)));
        assertThrows(SecurityException.class,
            () -> taskService.getTaskReportResultByTask(taskId, projectId, "stranger"));
        verify(taskFileRepository, never()).findByTaskIdOrderByCreatedAtAsc(anyString());
    }

    @Test
    void reportResult_readOnlyMemberAllowed() {
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(newTask(projectId)));
        when(permissionRepository.findByUserIdAndProjectId("reader", projectId)).thenReturn(Optional.of(
            new UserProjectPermission("p1", "reader", projectId, UserProjectPermission.Permission.READ_ONLY)));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(Collections.emptyList());

        TaskReportResultResponse resp = taskService.getTaskReportResultByTask(taskId, projectId, "reader");
        assertEquals(0, resp.getTotal());
    }

    @Test
    void taskList_defaultScopeReturnsOwnTasksOnly() {
        when(taskRepository.findByProjectIdAndUserIdOrderByCreatedAtDesc(projectId, ownerId))
            .thenReturn(Collections.singletonList(newTask(projectId)));

        TaskListResponse resp = taskService.getTaskList(projectId, ownerId, null);

        assertEquals(1, resp.getTotalCount());
        verify(taskRepository, never()).findByProjectIdOrderByCreatedAtDesc(anyString());
    }

    @Test
    void taskList_scopeAllReturnsProjectTasks() {
        when(taskRepository.findByProjectIdOrderByCreatedAtDesc(projectId))
            .thenReturn(Collections.singletonList(newTask(projectId)));

        TaskListResponse resp = taskService.getTaskList(projectId, ownerId, "ALL");

        assertEquals(1, resp.getTotalCount());
        verify(taskRepository, never()).findByProjectIdAndUserIdOrderByCreatedAtDesc(anyString(), anyString());
    }

    @Test
    void taskList_invalidScope() {
        assertThrows(IllegalArgumentException.class, () -> taskService.getTaskList(projectId, ownerId, "foo"));
    }

    @Test
    void geometryToBBox_variants() {
        assertEquals(Arrays.asList(1.0, 2.0, 4.0, 6.0),
            TaskService.geometryToBBox("{\"type\":\"rect\",\"x\":1,\"y\":2,\"w\":3,\"h\":4}"));
        assertEquals(Arrays.asList(1.0, 2.0, 3.0, 4.0), TaskService.geometryToBBox("[1,2,3,4]"));
        assertEquals(Arrays.asList(0.0, 1.0, 5.0, 9.0),
            TaskService.geometryToBBox("{\"type\":\"polygon\",\"points\":[[0,9],[5,1],{\"x\":2,\"y\":3}]}"));
        assertNull(TaskService.geometryToBBox(null));
        assertNull(TaskService.geometryToBBox("not json"));
        assertNull(TaskService.geometryToBBox("{\"type\":\"unknown\"}"));
    }
}
