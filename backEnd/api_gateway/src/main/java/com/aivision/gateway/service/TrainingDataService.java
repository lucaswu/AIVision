package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.TrainingDataSourceRepository;
import com.aivision.gateway.repository.TrainingDatasetRepository;
import com.aivision.gateway.repository.TrainingDatasetSourceRepository;
import com.aivision.gateway.repository.TrainingJobRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@Transactional
public class TrainingDataService {

    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final List<TrainingJobStatus> ACTIVE_JOB_STATUSES =
            Arrays.asList(TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING);

    @Autowired
    private TrainingDataSourceRepository dataSourceRepository;

    @Autowired
    private TrainingDatasetRepository datasetRepository;

    @Autowired
    private TrainingDatasetSourceRepository datasetSourceRepository;

    @Autowired
    private TrainingJobRepository trainingJobRepository;

    @Autowired
    private ProjectRepository projectRepository;

    @Autowired
    private UserProjectPermissionRepository permissionRepository;

    @Autowired
    private UserRepository userRepository;

    @Value("${storage.local.base-dir:/data/files}")
    private String localBaseDir;

    public TrainingDataSummary getSummary(String projectId, String userId) {
        validateTrainingProject(projectId, userId);

        List<TrainingDataSource> sources = dataSourceRepository.findByProjectIdOrderByCreatedAtDesc(projectId);
        int labeledCount = 0;
        int rawCount = 0;
        for (TrainingDataSource source : sources) {
            int fileCount = source.getFileCount() != null ? source.getFileCount() : 0;
            int labeled = source.getLabeledCount() != null ? source.getLabeledCount() : 0;
            labeledCount += labeled;
            rawCount += Math.max(fileCount - labeled, 0);
        }

        int datasetCount = (int) datasetRepository.countByProjectId(projectId);
        int dataSourceCount = (int) dataSourceRepository.countByProjectId(projectId);

        return new TrainingDataSummary(rawCount, labeledCount, datasetCount, dataSourceCount);
    }

    public List<TrainingDataSourceItem> getDataSources(String projectId, String userId) {
        validateTrainingProject(projectId, userId);

        List<TrainingDataSource> sources = dataSourceRepository.findByProjectIdOrderByCreatedAtDesc(projectId);
        if (sources.isEmpty()) {
            return Collections.emptyList();
        }

        List<String> sourceIds = sources.stream()
                .map(TrainingDataSource::getSourceId)
                .collect(Collectors.toList());

        List<TrainingDataset> datasets = datasetRepository.findByProjectIdOrderByCreatedAtDesc(projectId);
        Map<String, String> datasetNameMap = datasets.stream()
                .collect(Collectors.toMap(TrainingDataset::getDatasetId, TrainingDataset::getName));

        List<TrainingDatasetSource> datasetSources = datasetSourceRepository.findBySourceIdIn(sourceIds);
        Map<String, Set<String>> sourceToDatasetIds = new HashMap<>();
        for (TrainingDatasetSource link : datasetSources) {
            sourceToDatasetIds
                    .computeIfAbsent(link.getSourceId(), key -> new HashSet<>())
                    .add(link.getDatasetId());
        }

        Map<String, List<String>> datasetToActiveJobs = getDatasetActiveJobNames(projectId);

        List<TrainingDataSourceItem> items = new ArrayList<>();
        for (TrainingDataSource source : sources) {
            Set<String> datasetIds = sourceToDatasetIds.getOrDefault(source.getSourceId(), Collections.emptySet());
            List<String> usedByDatasets = datasetIds.stream()
                    .map(datasetId -> {
                        String name = datasetNameMap.get(datasetId);
                        return name != null && !name.trim().isEmpty() ? name : datasetId;
                    })
                    .distinct()
                    .collect(Collectors.toList());

            List<String> usedByExperiments = datasetIds.stream()
                    .flatMap(datasetId -> datasetToActiveJobs.getOrDefault(datasetId, Collections.emptyList()).stream())
                    .distinct()
                    .collect(Collectors.toList());

            items.add(toDataSourceItem(source, usedByDatasets, usedByExperiments));
        }

        return items;
    }

    public TrainingDataSourceItem createDataSource(String projectId, String userId, CreateTrainingDataSourceRequest request) {
        validateTrainingProject(projectId, userId);

        if (request == null) {
            throw new IllegalArgumentException("请求参数不能为空");
        }

        String name = request.getName() != null ? request.getName().trim() : "";
        String path = request.getPath() != null ? request.getPath().trim() : "";
        if (name.isEmpty()) {
            throw new IllegalArgumentException("数据源名称不能为空");
        }
        if (path.isEmpty()) {
            throw new IllegalArgumentException("数据源路径不能为空");
        }

        TrainingDataSource source = new TrainingDataSource();
        source.setSourceId(UUID.randomUUID().toString());
        source.setProjectId(projectId);
        source.setName(name);
        source.setPath(path);
        source.setFileCount(request.getFileCount() != null ? request.getFileCount() : 0);
        source.setLabeledCount(request.getLabeledCount() != null ? request.getLabeledCount() : 0);
        source.setSizeBytes(request.getSizeBytes() != null ? request.getSizeBytes() : 0L);

        TrainingDataSource saved = dataSourceRepository.save(source);
        return toDataSourceItem(saved, Collections.emptyList(), Collections.emptyList());
    }

    public TrainingDataSourceItem uploadDataSource(String projectId, String userId, String sourceName, MultipartFile[] files) {
        validateTrainingProject(projectId, userId);

        if (files == null || files.length == 0) {
            throw new IllegalArgumentException("请选择需要上传的文件");
        }

        String resolvedName = sourceName != null ? sourceName.trim() : "";
        if (resolvedName.isEmpty()) {
            resolvedName = inferFolderName(files[0].getOriginalFilename());
        }
        if (resolvedName.isEmpty()) {
            throw new IllegalArgumentException("数据源名称不能为空");
        }

        String sourceId = UUID.randomUUID().toString();
        Path basePath = Paths.get(localBaseDir, "training", projectId, sourceId);
        try {
            Files.createDirectories(basePath);
        } catch (IOException e) {
            throw new RuntimeException("创建数据源目录失败: " + e.getMessage());
        }

        int fileCount = 0;
        long sizeBytes = 0L;
        for (MultipartFile file : files) {
            if (file == null || file.isEmpty()) {
                continue;
            }
            String originalName = file.getOriginalFilename();
            String relativePath = sanitizeRelativePath(originalName);
            if (relativePath.isEmpty()) {
                relativePath = file.getName();
            }
            Path targetPath = basePath.resolve(relativePath).normalize();
            if (!targetPath.startsWith(basePath)) {
                throw new RuntimeException("非法文件路径: " + originalName);
            }
            try {
                Files.createDirectories(targetPath.getParent());
                Files.copy(file.getInputStream(), targetPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException e) {
                throw new RuntimeException("文件上传失败: " + e.getMessage());
            }
            fileCount += 1;
            sizeBytes += file.getSize();
        }

        TrainingDataSource source = new TrainingDataSource();
        source.setSourceId(sourceId);
        source.setProjectId(projectId);
        source.setName(resolvedName);
        source.setPath(basePath.toString());
        source.setFileCount(fileCount);
        source.setLabeledCount(0);
        source.setSizeBytes(sizeBytes);

        TrainingDataSource saved = dataSourceRepository.save(source);
        return toDataSourceItem(saved, Collections.emptyList(), Collections.emptyList());
    }

    public void deleteDataSource(String projectId, String userId, String sourceId) {
        validateTrainingProject(projectId, userId);

        TrainingDataSource source = dataSourceRepository.findById(sourceId)
                .orElseThrow(() -> new IllegalArgumentException("数据源不存在"));
        if (!projectId.equals(source.getProjectId())) {
            throw new IllegalArgumentException("数据源不属于当前项目");
        }

        List<TrainingDatasetSource> links = datasetSourceRepository.findBySourceId(sourceId);
        Set<String> datasetIds = links.stream()
                .map(TrainingDatasetSource::getDatasetId)
                .collect(Collectors.toSet());
        if (datasetIds.size() > 1) {
            throw new RuntimeException("数据源已被多个数据集引用，无法删除");
        }

        if (!links.isEmpty()) {
            datasetSourceRepository.deleteAll(links);
            if (datasetIds.size() == 1) {
                String datasetId = datasetIds.iterator().next();
                recalculateDatasetCount(datasetId);
            }
        }

        dataSourceRepository.delete(source);
    }

    public List<TrainingDatasetItem> getDatasets(String projectId, String userId) {
        validateTrainingProject(projectId, userId);

        List<TrainingDataset> datasets = datasetRepository.findByProjectIdOrderByCreatedAtDesc(projectId);
        if (datasets.isEmpty()) {
            return Collections.emptyList();
        }

        List<String> datasetIds = datasets.stream()
                .map(TrainingDataset::getDatasetId)
                .collect(Collectors.toList());
        List<TrainingDatasetSource> datasetSources = datasetSourceRepository.findByDatasetIdIn(datasetIds);
        Map<String, List<String>> datasetToSourceIds = new HashMap<>();
        for (TrainingDatasetSource link : datasetSources) {
            datasetToSourceIds
                    .computeIfAbsent(link.getDatasetId(), key -> new ArrayList<>())
                    .add(link.getSourceId());
        }

        List<String> sourceIds = datasetSources.stream()
                .map(TrainingDatasetSource::getSourceId)
                .distinct()
                .collect(Collectors.toList());
        Map<String, String> sourceNameMap = new HashMap<>();
        if (!sourceIds.isEmpty()) {
            dataSourceRepository.findAllById(sourceIds).forEach(source ->
                    sourceNameMap.put(source.getSourceId(), source.getName()));
        }

        Map<String, List<String>> datasetToActiveJobs = getDatasetActiveJobNames(projectId);

        List<TrainingDatasetItem> items = new ArrayList<>();
        for (TrainingDataset dataset : datasets) {
            List<String> sourceIdList = datasetToSourceIds.getOrDefault(dataset.getDatasetId(), Collections.emptyList());
            List<String> sourceNames = sourceIdList.stream()
                    .map(sourceNameMap::get)
                    .filter(name -> name != null && !name.trim().isEmpty())
                    .distinct()
                    .collect(Collectors.toList());

            String sourceSummary = String.join(", ", sourceNames);

            items.add(toDatasetItem(dataset, sourceSummary, sourceIdList,
                    datasetToActiveJobs.getOrDefault(dataset.getDatasetId(), Collections.emptyList())));
        }

        return items;
    }

    public TrainingDatasetItem createDataset(String projectId, String userId, CreateTrainingDatasetRequest request) {
        validateTrainingProject(projectId, userId);

        if (request == null) {
            throw new IllegalArgumentException("请求参数不能为空");
        }

        String name = request.getName() != null ? request.getName().trim() : "";
        if (name.isEmpty()) {
            throw new IllegalArgumentException("数据集名称不能为空");
        }

        TrainingDatasetType datasetType = normalizeDatasetType(request.getType());
        if (datasetType == null) {
            throw new IllegalArgumentException("数据集类型不合法");
        }

        List<String> sourceIds = request.getSourceIds() != null ? request.getSourceIds() : Collections.emptyList();
        if (sourceIds.isEmpty()) {
            throw new IllegalArgumentException("请选择至少一个数据源");
        }

        List<TrainingDataSource> sources = dataSourceRepository.findAllById(sourceIds);
        if (sources.size() != sourceIds.size()) {
            throw new IllegalArgumentException("存在无效的数据源ID");
        }

        for (TrainingDataSource source : sources) {
            if (!projectId.equals(source.getProjectId())) {
                throw new IllegalArgumentException("数据源不属于当前项目");
            }
        }

        TrainingDataset dataset = new TrainingDataset();
        dataset.setDatasetId(UUID.randomUUID().toString());
        dataset.setProjectId(projectId);
        dataset.setName(name);
        dataset.setDatasetType(datasetType);
        dataset.setTotalCount(calculateTotalCount(sources));

        TrainingDataset saved = datasetRepository.save(dataset);

        List<TrainingDatasetSource> links = sourceIds.stream()
                .map(sourceId -> new TrainingDatasetSource(UUID.randomUUID().toString(), saved.getDatasetId(), sourceId))
                .collect(Collectors.toList());
        datasetSourceRepository.saveAll(links);

        String sourceSummary = sources.stream()
                .map(TrainingDataSource::getName)
                .filter(sourceName -> sourceName != null && !sourceName.trim().isEmpty())
                .collect(Collectors.joining(", "));

        return toDatasetItem(saved, sourceSummary, sourceIds, Collections.emptyList());
    }

    public void deleteDataset(String projectId, String userId, String datasetId) {
        validateTrainingProject(projectId, userId);

        TrainingDataset dataset = datasetRepository.findById(datasetId)
                .orElseThrow(() -> new IllegalArgumentException("数据集不存在"));
        if (!projectId.equals(dataset.getProjectId())) {
            throw new IllegalArgumentException("数据集不属于当前项目");
        }

        long activeJobCount = trainingJobRepository.countByDatasetIdAndStatusIn(datasetId, ACTIVE_JOB_STATUSES);
        if (activeJobCount > 0) {
            throw new RuntimeException("数据集正在被训练任务使用，无法删除");
        }

        List<TrainingDatasetSource> links = datasetSourceRepository.findByDatasetId(datasetId);
        if (!links.isEmpty()) {
            datasetSourceRepository.deleteAll(links);
        }

        datasetRepository.delete(dataset);
    }

    private void recalculateDatasetCount(String datasetId) {
        TrainingDataset dataset = datasetRepository.findById(datasetId).orElse(null);
        if (dataset == null) {
            return;
        }

        List<TrainingDatasetSource> remainingLinks = datasetSourceRepository.findByDatasetId(datasetId);
        if (remainingLinks.isEmpty()) {
            dataset.setTotalCount(0);
            datasetRepository.save(dataset);
            return;
        }

        List<String> remainingSourceIds = remainingLinks.stream()
                .map(TrainingDatasetSource::getSourceId)
                .collect(Collectors.toList());
        List<TrainingDataSource> remainingSources = dataSourceRepository.findAllById(remainingSourceIds);
        dataset.setTotalCount(calculateTotalCount(remainingSources));
        datasetRepository.save(dataset);
    }

    private int calculateTotalCount(List<TrainingDataSource> sources) {
        int total = 0;
        for (TrainingDataSource source : sources) {
            total += source.getFileCount() != null ? source.getFileCount() : 0;
        }
        return total;
    }

    private TrainingDatasetType normalizeDatasetType(String rawType) {
        if (rawType == null) {
            return null;
        }
        String normalized = rawType.trim().toUpperCase();
        if ("TRAIN".equals(normalized) || "训练集".equals(rawType.trim())) {
            return TrainingDatasetType.TRAIN;
        }
        if ("TEST".equals(normalized) || "测试集".equals(rawType.trim())) {
            return TrainingDatasetType.TEST;
        }
        return null;
    }

    private String inferFolderName(String originalName) {
        if (originalName == null) {
            return "";
        }
        String normalized = originalName.replace("\\", "/");
        int index = normalized.indexOf("/");
        if (index > 0) {
            return normalized.substring(0, index);
        }
        return "";
    }

    private String sanitizeRelativePath(String originalName) {
        if (originalName == null) {
            return "";
        }
        String normalized = originalName.replace("\\", "/");
        while (normalized.startsWith("/")) {
            normalized = normalized.substring(1);
        }
        if (normalized.contains("..")) {
            normalized = normalized.replace("..", "");
        }
        return normalized;
    }

    private TrainingDataSourceItem toDataSourceItem(TrainingDataSource source,
                                                    List<String> usedByDatasets,
                                                    List<String> usedByExperiments) {
        String createTime = source.getCreatedAt() != null ? source.getCreatedAt().format(DATE_TIME_FORMATTER) : "";
        String updateTime = source.getUpdatedAt() != null ? source.getUpdatedAt().format(DATE_TIME_FORMATTER) : "";
        return new TrainingDataSourceItem(
                source.getSourceId(),
                source.getName(),
                source.getPath(),
                source.getFileCount() != null ? source.getFileCount() : 0,
                source.getLabeledCount() != null ? source.getLabeledCount() : 0,
                source.getSizeBytes() != null ? source.getSizeBytes() : 0L,
                createTime,
                updateTime,
                usedByDatasets,
                usedByExperiments
        );
    }

    private TrainingDatasetItem toDatasetItem(TrainingDataset dataset,
                                              String sourceSummary,
                                              List<String> sourceIds,
                                              List<String> inUseExperiments) {
        String createTime = dataset.getCreatedAt() != null ? dataset.getCreatedAt().format(DATE_TIME_FORMATTER) : "";
        String typeLabel = dataset.getDatasetType() == TrainingDatasetType.TEST ? "测试集" : "训练集";
        return new TrainingDatasetItem(
                dataset.getDatasetId(),
                dataset.getName(),
                typeLabel,
                dataset.getTotalCount() != null ? dataset.getTotalCount() : 0,
                sourceSummary,
                sourceIds,
                createTime,
                inUseExperiments
        );
    }

    private Map<String, List<String>> getDatasetActiveJobNames(String projectId) {
        List<TrainingJob> activeJobs = trainingJobRepository.findByProjectIdAndStatusIn(projectId, ACTIVE_JOB_STATUSES);
        if (activeJobs.isEmpty()) {
            return Collections.emptyMap();
        }

        Map<String, List<String>> datasetToJobs = new HashMap<>();
        for (TrainingJob job : activeJobs) {
            String displayName = job.getJobName();
            if (displayName == null || displayName.trim().isEmpty()) {
                displayName = job.getJobId();
            }
            datasetToJobs
                    .computeIfAbsent(job.getDatasetId(), key -> new ArrayList<>())
                    .add(displayName);
        }
        return datasetToJobs;
    }

    private void validateTrainingProject(String projectId, String userId) {
        if (projectId == null || projectId.trim().isEmpty()) {
            throw new IllegalArgumentException("项目ID不能为空");
        }
        if (userId == null || userId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }

        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new IllegalArgumentException("项目不存在"));
        String projectType = project.getProjectType() != null ? project.getProjectType().trim() : "";
        if (!"AI_TRAINING".equalsIgnoreCase(projectType)) {
            throw new IllegalArgumentException("非训练项目，无法访问数据管理");
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        if (user.hasRole("ADMIN")) {
            return;
        }

        if (project.getOwnerId() != null && project.getOwnerId().equals(userId)) {
            return;
        }

        boolean hasPermission = permissionRepository.findByUserIdAndProjectId(userId, projectId).isPresent();
        if (!hasPermission) {
            throw new RuntimeException("无权限访问该项目");
        }
    }
}
