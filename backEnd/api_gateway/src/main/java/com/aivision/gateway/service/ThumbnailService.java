package com.aivision.gateway.service;

import com.aivision.gateway.model.File;
import com.aivision.gateway.model.ThumbnailTask;
import com.aivision.gateway.model.User;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ThumbnailTaskRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.time.LocalDateTime;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.MemoryCacheImageOutputStream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

/**
 * 缩略图生成与读取服务。
 *
 * <p>上传线程只负责入队，后台定时从数据库取任务处理，避免大目录上传时内存队列溢出后静默丢任务。
 */
@Service
public class ThumbnailService {

    private static final Logger logger = LoggerFactory.getLogger(ThumbnailService.class);
    private static final Set<String> DIRECT_IMAGEIO_EXTENSIONS = Set.of("bmp");
    private static final Set<String> AI_CONVERT_EXTENSIONS = Set.of("tif", "tiff", "dcm", "dicom", "dic", "diconde");
    private static final int MAX_ATTEMPTS = 5;

    /** JPEG 压缩质量，0.0~1.0 */
    private static final float JPEG_QUALITY = 0.85f;

    @Value("${thumbnail.http.connect-timeout-ms:5000}")
    private int httpConnectTimeoutMs;

    @Value("${thumbnail.http.read-timeout-ms:120000}")
    private int httpReadTimeoutMs;

    // 带超时的 RestTemplate：避免推理服务慢/无响应时，单线程调度器无限期阻塞、缩略图队列堆积
    private RestTemplate restTemplate;

    @javax.annotation.PostConstruct
    void initRestTemplate() {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
            new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(httpConnectTimeoutMs);
        factory.setReadTimeout(httpReadTimeoutMs);
        this.restTemplate = new RestTemplate(factory);
    }

    @Autowired
    private StorageStrategy storageStrategy;

    @Autowired
    private FileRepository fileRepository;

    @Autowired
    private ThumbnailTaskRepository thumbnailTaskRepository;

    @Autowired
    private UserRepository userRepository;

    @Value("${ai-services.inference-url:http://ai-inference:8000}")
    private String inferenceServiceUrl;

    @Value("${thumbnail.worker.batch-size:20}")
    private int thumbnailWorkerBatchSize;

    // ──────────────────────────────────────────────────────────────────────────
    // 入队与后台生成
    // ──────────────────────────────────────────────────────────────────────────

    @Transactional
    public void enqueueGeneration(String fileId) {
        if (fileId == null || fileId.isBlank()) {
            return;
        }

        Optional<File> fileOpt = fileRepository.findById(fileId);
        if (fileOpt.isEmpty()) {
            logger.warn("ThumbnailService: 入队失败，文件不存在, fileId={}", fileId);
            return;
        }

        File file = fileOpt.get();
        if (!supportsThumbnailGeneration(file.getFileExtension())) {
            return;
        }
        if (file.getThumbnailPath() != null && !file.getThumbnailPath().isBlank()) {
            return;
        }

        ThumbnailTask task = thumbnailTaskRepository.findByFileId(fileId)
            .orElseGet(() -> new ThumbnailTask(UUID.randomUUID().toString(), fileId));

        if (task.getStatus() == ThumbnailTask.Status.DONE || task.getStatus() == ThumbnailTask.Status.PROCESSING) {
            return;
        }

        task.setStatus(ThumbnailTask.Status.PENDING);
        task.setNextRunAt(LocalDateTime.now());
        thumbnailTaskRepository.save(task);
    }

    /**
     * 批量入队：供上传事务提交后调用。一次查询 + 一次批量插入，同步执行在调用线程上，
     * 不再走 @Async 线程池（线程池饱和时 CallerRunsPolicy 会把入队压回 Tomcat 上传线程，
     * 拖慢上传响应）。fileIds 已在 processFile 阶段确认支持缩略图生成。
     */
    @Transactional
    public void enqueueBatch(List<String> fileIds) {
        if (fileIds == null || fileIds.isEmpty()) {
            return;
        }

        java.util.Set<String> existing = new java.util.HashSet<>();
        for (ThumbnailTask t : thumbnailTaskRepository.findByFileIdIn(fileIds)) {
            existing.add(t.getFileId());
        }

        List<ThumbnailTask> toInsert = new java.util.ArrayList<>();
        LocalDateTime now = LocalDateTime.now();
        for (String fileId : fileIds) {
            if (fileId == null || fileId.isBlank() || existing.contains(fileId)) {
                continue;
            }
            ThumbnailTask task = new ThumbnailTask(UUID.randomUUID().toString(), fileId);
            task.setStatus(ThumbnailTask.Status.PENDING);
            task.setNextRunAt(now);
            toInsert.add(task);
        }

        if (!toInsert.isEmpty()) {
            thumbnailTaskRepository.saveAll(toInsert);
        }
    }

    @Scheduled(fixedDelayString = "${thumbnail.worker.fixed-delay-ms:3000}")
    public void drainQueue() {
        resetStaleProcessingTasks();
        List<ThumbnailTask.Status> retryableStatuses = new java.util.ArrayList<>();
        retryableStatuses.add(ThumbnailTask.Status.PENDING);
        retryableStatuses.add(ThumbnailTask.Status.FAILED);
        List<ThumbnailTask> tasks = thumbnailTaskRepository
            .findByStatusInAndNextRunAtLessThanEqualOrderByCreatedAtAsc(
                retryableStatuses,
                LocalDateTime.now(),
                PageRequest.of(0, Math.max(thumbnailWorkerBatchSize, 1)));

        for (ThumbnailTask task : tasks) {
            processQueuedTask(task.getTaskId());
        }
    }

    private void resetStaleProcessingTasks() {
        LocalDateTime cutoff = LocalDateTime.now().minusMinutes(30);
        List<ThumbnailTask> staleTasks = thumbnailTaskRepository.findByStatusAndUpdatedAtLessThan(
            ThumbnailTask.Status.PROCESSING, cutoff);
        for (ThumbnailTask task : staleTasks) {
            task.setStatus(ThumbnailTask.Status.FAILED);
            task.setNextRunAt(LocalDateTime.now());
            task.setLastError("缩略图任务处理超时，已重新排队");
            thumbnailTaskRepository.save(task);
        }
        if (!staleTasks.isEmpty()) {
            logger.warn("ThumbnailService: 已重新排队 {} 个超时缩略图任务", staleTasks.size());
        }
    }

    @Transactional
    public void processQueuedTask(String taskId) {
        Optional<ThumbnailTask> taskOpt = thumbnailTaskRepository.findById(taskId);
        if (taskOpt.isEmpty()) {
            return;
        }

        ThumbnailTask task = taskOpt.get();
        if (task.getStatus() == ThumbnailTask.Status.PROCESSING || task.getStatus() == ThumbnailTask.Status.DONE) {
            return;
        }

        task.setStatus(ThumbnailTask.Status.PROCESSING);
        thumbnailTaskRepository.save(task);

        try {
            generateAndStoreNow(task.getFileId());
            task.setStatus(ThumbnailTask.Status.DONE);
            task.setLastError(null);
            task.setNextRunAt(null);
            thumbnailTaskRepository.save(task);
        } catch (Exception e) {
            int attempts = task.getAttemptCount() == null ? 1 : task.getAttemptCount() + 1;
            task.setAttemptCount(attempts);
            task.setLastError(trimError(e.getMessage()));
            if (attempts >= MAX_ATTEMPTS) {
                task.setStatus(ThumbnailTask.Status.ABANDONED);
                task.setNextRunAt(null);
            } else {
                task.setStatus(ThumbnailTask.Status.FAILED);
                task.setNextRunAt(LocalDateTime.now().plusSeconds(backoffSeconds(attempts)));
            }
            thumbnailTaskRepository.save(task);
            logger.warn("ThumbnailService: 缩略图任务失败, fileId={}, attempt={}, reason={}",
                task.getFileId(), attempts, e.getMessage());
        }
    }

    public boolean supportsThumbnailGeneration(String fileExtension) {
        if (fileExtension == null || fileExtension.isBlank()) {
            return false;
        }
        String normalized = fileExtension.trim().toLowerCase();
        return DIRECT_IMAGEIO_EXTENSIONS.contains(normalized) || AI_CONVERT_EXTENSIONS.contains(normalized);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 读取缩略图（Controller 调用）
    // ──────────────────────────────────────────────────────────────────────────

    public byte[] getThumbnailBytes(String fileId, String projectId, String userId) {
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        Optional<File> fileOpt;
        if (user.getRole() == User.Role.ADMIN) {
            fileOpt = fileRepository.findByFileIdAndProjectId(fileId, projectId);
        } else {
            fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
        }

        File file = fileOpt.orElseThrow(() -> new IllegalArgumentException("文件不存在或无权限访问"));

        String thumbPath = file.getThumbnailPath();
        if (thumbPath == null || thumbPath.isBlank()) {
            enqueueGeneration(file.getFileId());
            return null;
        }

        try (InputStream is = storageStrategy.download(thumbPath)) {
            return is.readAllBytes();
        } catch (Exception e) {
            logger.warn("ThumbnailService: 读取缩略图失败, fileId={}, thumbPath={}, 原因={}", fileId, thumbPath, e.getMessage());
            enqueueGeneration(file.getFileId());
            return null;
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 内部工具方法
    // ──────────────────────────────────────────────────────────────────────────

    private void generateAndStoreNow(String fileId) throws Exception {
        Optional<File> fileOpt = fileRepository.findById(fileId);
        if (fileOpt.isEmpty()) {
            throw new IllegalArgumentException("文件不存在");
        }

        File file = fileOpt.get();
        if (file.getThumbnailPath() != null && !file.getThumbnailPath().isBlank()) {
            return;
        }

        byte[] jpegBytes = generateThumbnailBytes(file);
        if (jpegBytes == null || jpegBytes.length == 0) {
            throw new IllegalStateException("无法生成缩略图");
        }

        String thumbPath = file.getFilePath() + ".thumb.jpg";
        storageStrategy.upload(
            new ByteArrayInputStream(jpegBytes),
            thumbPath,
            "image/jpeg",
            jpegBytes.length
        );

        file.setThumbnailPath(thumbPath);
        fileRepository.save(file);

        logger.info("ThumbnailService: 缩略图生成成功, fileId={}, thumbPath={}, 缩略图={}KB",
            fileId, thumbPath, jpegBytes.length / 1024);
    }

    private byte[] encodeJpeg(BufferedImage image, float quality) throws Exception {
        Iterator<ImageWriter> writers = ImageIO.getImageWritersByFormatName("jpeg");
        if (!writers.hasNext()) {
            throw new IllegalStateException("系统不支持 JPEG 编码器");
        }
        ImageWriter writer = writers.next();

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (MemoryCacheImageOutputStream output = new MemoryCacheImageOutputStream(baos)) {
            writer.setOutput(output);

            ImageWriteParam param = writer.getDefaultWriteParam();
            param.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);
            param.setCompressionQuality(quality);

            writer.write(null, new IIOImage(image, null, null), param);
        } finally {
            writer.dispose();
        }
        return baos.toByteArray();
    }

    private byte[] generateThumbnailBytes(File file) throws Exception {
        String extension = file.getFileExtension() == null ? "" : file.getFileExtension().trim().toLowerCase();

        if (AI_CONVERT_EXTENSIONS.contains(extension)) {
            return convertViaAiService(file);
        }

        try (InputStream is = storageStrategy.download(file.getFilePath())) {
            BufferedImage image = ImageIO.read(is);
            if (image == null) {
                return null;
            }

            BufferedImage rgbImage = image;
            if (image.getType() != BufferedImage.TYPE_INT_RGB &&
                image.getType() != BufferedImage.TYPE_3BYTE_BGR) {
                rgbImage = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
                rgbImage.createGraphics().drawImage(image, 0, 0, null);
            }

            return encodeJpeg(rgbImage, JPEG_QUALITY);
        }
    }

    private byte[] convertViaAiService(File file) throws Exception {
        String sharedPath = storageStrategy.resolveSharedPath(file.getFilePath());
        if (sharedPath != null && !sharedPath.isBlank()) {
            try {
                return convertViaAiServicePath(file, sharedPath);
            } catch (Exception e) {
                logger.warn("ThumbnailService: 按路径转换失败，回退为流式上传, fileId={}, reason={}", file.getFileId(), e.getMessage());
            }
        }
        return convertViaAiServiceUpload(file);
    }

    private byte[] convertViaAiServicePath(File file, String sharedPath) {
        String url = inferenceServiceUrl + "/thumbnail/convert-path";
        java.nio.file.Path localPath = java.nio.file.Paths.get(sharedPath);
        if (!java.nio.file.Files.exists(localPath)) {
            throw new IllegalArgumentException("共享路径不存在: " + sharedPath);
        }
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("path", sharedPath);
        body.add("filename", resolveUploadFilename(file));
        body.add("quality", Integer.toString(Math.round(JPEG_QUALITY * 100)));

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        ResponseEntity<byte[]> response = restTemplate.postForEntity(
            url,
            new HttpEntity<>(body, headers),
            byte[].class
        );

        return validateAiResponse(response);
    }

    private byte[] convertViaAiServiceUpload(File file) throws Exception {
        byte[] originalBytes;
        try (InputStream is = storageStrategy.download(file.getFilePath())) {
            originalBytes = is.readAllBytes();
        }

        String url = inferenceServiceUrl + "/thumbnail/convert";
        String filename = resolveUploadFilename(file);

        ByteArrayResource resource = new ByteArrayResource(originalBytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        };

        HttpHeaders partHeaders = new HttpHeaders();
        partHeaders.setContentType(MediaType.APPLICATION_OCTET_STREAM);
        partHeaders.setContentDispositionFormData("file", filename);
        HttpEntity<ByteArrayResource> filePart = new HttpEntity<>(resource, partHeaders);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", filePart);
        body.add("quality", Integer.toString(Math.round(JPEG_QUALITY * 100)));

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        ResponseEntity<byte[]> response = restTemplate.postForEntity(
            url,
            new HttpEntity<>(body, headers),
            byte[].class
        );

        return validateAiResponse(response);
    }

    private byte[] validateAiResponse(ResponseEntity<byte[]> response) {
        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null || response.getBody().length == 0) {
            throw new IllegalStateException("AI 服务未返回有效 JPEG 缩略图");
        }
        return response.getBody();
    }

    private String resolveUploadFilename(File file) {
        if (file.getOriginalName() != null && !file.getOriginalName().isBlank()) {
            return file.getOriginalName();
        }
        if (file.getStoredName() != null && !file.getStoredName().isBlank()) {
            return file.getStoredName();
        }
        String extension = file.getFileExtension() == null || file.getFileExtension().isBlank()
            ? "img"
            : file.getFileExtension().trim().toLowerCase();
        return file.getFileId() + "." + extension;
    }

    private long backoffSeconds(int attempts) {
        return Math.min(300L, (long) Math.pow(2, Math.max(attempts - 1, 0)) * 10L);
    }

    private String trimError(String message) {
        if (message == null) {
            return null;
        }
        return message.length() > 1000 ? message.substring(0, 1000) : message;
    }
}
