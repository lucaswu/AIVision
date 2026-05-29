package com.aivision.gateway.service;

import com.aivision.gateway.config.FileUploadProperties;
import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import java.nio.charset.StandardCharsets;
import org.apache.commons.io.FilenameUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.util.*;
import java.util.Base64;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
@Transactional
public class FileService {
    
    private static final Logger logger = LoggerFactory.getLogger(FileService.class);
    
    @Autowired
    private FileRepository fileRepository;
    
    @Autowired
    private ProjectRepository projectRepository;
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private UserProjectPermissionRepository permissionRepository;

    @Autowired
    private UserRepository userRepository;
    
    @Autowired
    private FileUploadProperties fileUploadProperties;
    
    @Autowired
    private StorageStrategy storageStrategy;

    @Autowired
    private ThumbnailService thumbnailService;

    @Autowired
    private UploadConfigService uploadConfigService;
    
    /**
     * 上传多个文件
     */
    public FileUploadResponse uploadFiles(String projectId, String userId, String directoryId, MultipartFile[] files) {
        return uploadFiles(projectId, userId, directoryId, files, null, null);
    }

    public FileUploadResponse uploadFiles(
            String projectId,
            String userId,
            String directoryId,
            MultipartFile[] files,
            String uploadSessionId,
            String[] uploadKeys) {
        logger.info("收到文件上传请求: project={}, user={}, directory={}, 文件数量={}", 
            projectId, userId, directoryId, files != null ? files.length : 0);
            
        List<FileUploadResponse.SuccessFileInfo> successFiles = new ArrayList<>();
        List<FileUploadResponse.FailedFileInfo> failedFiles = new ArrayList<>();
        
        // 1. 验证基础参数与权限
        if (!validateBasicParamsAndPermission(projectId, userId, directoryId, failedFiles)) {
            logger.warn("基础参数或权限验证失败: projectId={}, userId={}, directoryId={}", projectId, userId, directoryId);
            return new FileUploadResponse(0, failedFiles.size(), successFiles, failedFiles);
        }
        
        // 2. 获取目录信息 - 放宽权限检查，只要对项目有写权限即可
        Directory directory;
        try {
            directory = directoryRepository.findByDirIdAndProjectIdAndStatus(
                directoryId, projectId, Directory.Status.ACTIVE)
                .orElseThrow(() -> new IllegalArgumentException("目录不存在"));
            logger.info("获取到目录信息: {}, Path: {}", directory.getDirName(), directory.getDirPath());
        } catch (Exception e) {
            logger.error("获取目录信息失败: {}", e.getMessage());
            for (MultipartFile file : files) {
                failedFiles.add(new FileUploadResponse.FailedFileInfo(
                    file.getOriginalFilename(), "目录验证失败: " + e.getMessage()));
            }
            return new FileUploadResponse(0, failedFiles.size(), successFiles, failedFiles);
        }
        
        // 3. 计算总文件大小
        long totalSize = Arrays.stream(files)
                .mapToLong(MultipartFile::getSize)
                .sum();
        
        if (!validateTotalSize(totalSize, failedFiles, files)) {
            return new FileUploadResponse(0, failedFiles.size(), successFiles, failedFiles);
        }
        
        // 4. 逐个处理文件，收集需要生成缩略图的 fileId
        List<String> thumbnailFileIds = new ArrayList<>();
        for (int i = 0; i < files.length; i++) {
            MultipartFile file = files[i];
            String uploadKey = resolveUploadKey(uploadKeys, i);
            try {
                processFile(file, projectId, userId, directoryId, directory, successFiles, failedFiles,
                    thumbnailFileIds, normalizeBlank(uploadSessionId), uploadKey);
            } catch (Exception e) {
                failedFiles.add(new FileUploadResponse.FailedFileInfo(
                    file.getOriginalFilename(), "文件处理失败: " + e.getMessage()));
            }
        }

        // 5. 注册事务提交后回调，确保 DB 记录已可见再触发缩略图生成
        //    （批量上传时若在事务内触发，缩略图线程会因 findById 查不到记录而失败）
        if (!thumbnailFileIds.isEmpty()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    // 一次性批量入队，避免逐文件 @Async 提交在线程池饱和时回压到上传请求线程
                    thumbnailService.enqueueBatch(thumbnailFileIds);
                    logger.info("已批量入队缩略图任务（事务提交后）: 数量={}", thumbnailFileIds.size());
                }
            });
        }
        
        return new FileUploadResponse(successFiles.size(), failedFiles.size(), successFiles, failedFiles);
    }
    
    /**
     * 验证基础参数与权限
     */
    private boolean validateBasicParamsAndPermission(String projectId, String userId, String directoryId, 
                                       List<FileUploadResponse.FailedFileInfo> failedFiles) {
        if (userId == null || userId.trim().isEmpty()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "用户ID不能为空"));
            return false;
        }
        
        if (directoryId == null || directoryId.trim().isEmpty()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "目录ID不能为空"));
            return false;
        }

        // 验证项目是否存在
        Optional<Project> projectOpt = projectRepository.findById(projectId);
        if (!projectOpt.isPresent()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "项目不存在"));
            return false;
        }
        
        // 检查权限：只有管理员、项目所有者或有读写权限的用户可以上传
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        
        if (user.getRole() != User.Role.ADMIN && !projectOpt.get().getOwnerId().equals(userId)) {
            // 检查是否有读写权限
            Optional<UserProjectPermission> permission = permissionRepository.findByUserIdAndProjectId(userId, projectId);
            if (!permission.isPresent() || permission.get().getPermission() != UserProjectPermission.Permission.READ_WRITE) {
                failedFiles.add(new FileUploadResponse.FailedFileInfo("", "无权限在项目中上传文件"));
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * 验证总文件大小
     */
    private boolean validateTotalSize(long totalSize, List<FileUploadResponse.FailedFileInfo> failedFiles,
                                     MultipartFile[] files) {
        long maxTotalSizeBytes = uploadConfigService.getMaxTotalSizeBytes();

        if (totalSize > maxTotalSizeBytes) {
            String limitText = uploadConfigService.humanReadableSize(maxTotalSizeBytes);
            for (MultipartFile file : files) {
                failedFiles.add(new FileUploadResponse.FailedFileInfo(
                    file.getOriginalFilename(), "总文件大小超过" + limitText + "限制"));
            }
            return false;
        }

        return true;
    }
    /**
     * 处理单个文件
     * @param thumbnailFileIds 收集需要生成缩略图的 fileId，用于事务提交后触发缩略图生成
     */
    private void processFile(MultipartFile file, String projectId, String userId, String directoryId,
                            Directory directory, List<FileUploadResponse.SuccessFileInfo> successFiles,
                            List<FileUploadResponse.FailedFileInfo> failedFiles, List<String> thumbnailFileIds,
                            String uploadSessionId, String uploadKey) {
        
        String originalFilename = file.getOriginalFilename();
        
        try {
            // 1. 验证文件
            if (!validateFile(file, failedFiles)) {
                return;
            }

            String normalizedUploadKey = normalizeBlank(uploadKey);
            Optional<File> existing = findExistingUpload(projectId, directoryId, uploadSessionId, normalizedUploadKey);
            if (existing.isPresent()) {
                File existingFile = existing.get();
                logger.info("命中幂等上传记录: project={}, directory={}, session={}, key={}, fileId={}",
                    projectId, directoryId, uploadSessionId, normalizedUploadKey, existingFile.getFileId());
                successFiles.add(new FileUploadResponse.SuccessFileInfo(
                    existingFile.getFileId(),
                    existingFile.getOriginalName(),
                    existingFile.getFileSize(),
                    existingFile.getFilePath()));
                if (thumbnailService.supportsThumbnailGeneration(existingFile.getFileExtension())) {
                    thumbnailFileIds.add(existingFile.getFileId());
                }
                return;
            }
            
            // 2. 生成文件信息
            String fileId = buildFileId(uploadSessionId, normalizedUploadKey);
            String fileExtension = FilenameUtils.getExtension(originalFilename).toLowerCase();
            String storedName = fileId + "." + fileExtension;
            String objectPath = buildObjectPath(projectId, userId, directory.getDirPath(), storedName);
            String fullPath = objectPath; // 逻辑路径
            
            // 3. 保存文件到存储服务 (Local or MinIO)
            String contentType = file.getContentType();
            if (contentType == null || contentType.trim().isEmpty()) {
                contentType = "application/octet-stream";
            }
            try (InputStream inputStream = file.getInputStream()) {
                storageStrategy.upload(inputStream, fullPath, contentType, file.getSize());
            }

            // 4. 保存到数据库（只存元数据，不存内容）
            File fileEntity = new File(
                fileId, projectId, userId, directoryId,
                originalFilename, storedName, fullPath,
                file.getSize(), contentType, fileExtension
            );
            fileEntity.setUploadSessionId(uploadSessionId);
            fileEntity.setUploadKey(normalizedUploadKey);
            
            fileRepository.save(fileEntity);

            // 5. 支持渐进式预览的文件记录到待处理列表（在事务提交后统一触发，避免竞态）
            if (thumbnailService.supportsThumbnailGeneration(fileExtension)) {
                thumbnailFileIds.add(fileId);
            }
            
            // 6. 添加到成功列表
            successFiles.add(new FileUploadResponse.SuccessFileInfo(
                fileId, originalFilename, file.getSize(), fullPath));
                
        } catch (Exception e) {
            logger.error("文件处理失败: {}, 错误: {}", originalFilename, e.getMessage(), e);
            failedFiles.add(new FileUploadResponse.FailedFileInfo(
                originalFilename, "文件上传失败: " + e.getMessage()));
        }
    }
    
    /**
     * 验证单个文件
     */
    private boolean validateFile(MultipartFile file, List<FileUploadResponse.FailedFileInfo> failedFiles) {
        String originalFilename = file.getOriginalFilename();
        
        // 验证文件是否为空
        if (file.isEmpty()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo(originalFilename, "文件为空"));
            return false;
        }
        
        // 验证文件大小（与 multipart max-file-size 配置统一，默认 200MB）
        long maxFileSizeBytes = uploadConfigService.getMaxFileSizeBytes();
        if (file.getSize() > maxFileSizeBytes) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo(
                originalFilename, "文件大小超过" + uploadConfigService.humanReadableSize(maxFileSizeBytes) + "限制"));
            return false;
        }
        
        // 验证文件类型
        String fileExtension = FilenameUtils.getExtension(originalFilename).toLowerCase();
        if (!fileUploadProperties.getAllowedImageTypes().contains(fileExtension)) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo(originalFilename, 
                "不支持的文件类型，仅支持: " + String.join(", ", fileUploadProperties.getAllowedImageTypes())));
            return false;
        }
        
        return true;
    }
    
    /**
     * 构建对象路径
     */
    private String buildObjectPath(String projectId, String userId, String dirPath, String storedName) {
        String normalizedDir = dirPath == null ? "" : dirPath;
        return String.format("/%s/%s%s/%s", projectId, userId, normalizedDir, storedName);
    }

    private String resolveUploadKey(String[] uploadKeys, int index) {
        if (uploadKeys == null || index >= uploadKeys.length) {
            return null;
        }
        return normalizeBlank(uploadKeys[index]);
    }

    private Optional<File> findExistingUpload(
            String projectId,
            String directoryId,
            String uploadSessionId,
            String uploadKey) {
        if (uploadSessionId == null || uploadKey == null) {
            return Optional.empty();
        }
        return fileRepository.findByProjectIdAndDirectoryIdAndUploadSessionIdAndUploadKey(
            projectId, directoryId, uploadSessionId, uploadKey);
    }

    private String buildFileId(String uploadSessionId, String uploadKey) {
        if (uploadSessionId == null || uploadKey == null) {
            return UUID.randomUUID().toString();
        }
        String raw = uploadSessionId + ":" + uploadKey;
        return UUID.nameUUIDFromBytes(raw.getBytes(StandardCharsets.UTF_8)).toString();
    }

    private String normalizeBlank(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
    
    /**
     * 获取文件图片数据 - 直接返回二进制数据
     */
    public FileImageData getFileImageData(String fileId, String projectId, String userId) {
        // 1. 验证用户角色：管理员可以查看项目中任何文件
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        
        Optional<File> fileOpt;
        if (user.getRole() == User.Role.ADMIN) {
            // 管理员权限：仅根据 fileId 和 projectId 查找
            fileOpt = fileRepository.findByFileIdAndProjectId(fileId, projectId);
        } else {
            // 普通用户：必须匹配本人上传的文件
            fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
        }

        if (!fileOpt.isPresent()) {
            logger.warn("文件查找失败: fileId={}, projectId={}, userId={}, role={}", fileId, projectId, userId, user.getRole());
            throw new IllegalArgumentException("文件不存在或无权限访问");
        }
        
        File file = fileOpt.get();
        
        // 2. 验证是否为图片文件
        if (!isImageFile(file.getFileExtension())) {
            throw new IllegalArgumentException("该文件不是图片格式，无法预览");
        }
        
        try {
            // 3. 从存储服务读取文件
            String rel = file.getFilePath();
            
            byte[] imageBytes;
            try (InputStream is = storageStrategy.download(rel)) {
                imageBytes = is.readAllBytes();
            }
            
            // 5. 确定Content-Type
            String contentType = file.getMimeType();
            if (contentType == null || contentType.trim().isEmpty()) {
                // 根据文件扩展名推断Content-Type
                contentType = inferContentTypeFromExtension(file.getFileExtension());
            }
            
            // 6. 构建并返回FileImageData
            return new FileImageData(
                imageBytes,
                contentType,
                file.getOriginalName(),
                file.getFileSize()
            );
            
        } catch (Exception e) {
            throw new RuntimeException("获取文件数据失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 获取文件预览
     */
    public FilePreviewResponse getFilePreview(String fileId, String projectId, String userId) {
        // 复用 getFileImageData 逻辑获取二进制数据
        FileImageData data = getFileImageData(fileId, projectId, userId);
        
        try {
            // 获取图片尺寸信息
            Integer width = null;
            Integer height = null;
            try {
                ByteArrayInputStream bis = new ByteArrayInputStream(data.getImageBytes());
                BufferedImage bufferedImage = ImageIO.read(bis);
                if (bufferedImage != null) {
                    width = bufferedImage.getWidth();
                    height = bufferedImage.getHeight();
                }
                bis.close();
            } catch (Exception e) {
                // 忽略尺寸获取失败
            }
            
            // 转换为Base64编码
            String base64Data = Base64.getEncoder().encodeToString(data.getImageBytes());
            String imageDataUrl = "data:" + data.getContentType() + ";base64," + base64Data;
            
            return new FilePreviewResponse(
                fileId,
                data.getFileName(),
                data.getFileSize(),
                data.getContentType(),
                imageDataUrl,
                width,
                height
            );
            
        } catch (Exception e) {
            throw new RuntimeException("获取文件预览失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 根据文件扩展名推断Content-Type
     */
    private String inferContentTypeFromExtension(String fileExtension) {
        switch (fileExtension.toLowerCase()) {
            case "jpg":
            case "jpeg":
                return "image/jpeg";
            case "png":
                return "image/png";
            case "gif":
                return "image/gif";
            case "bmp":
                return "image/bmp";
            case "webp":
                return "image/webp";
            case "svg":
                return "image/svg+xml";
            case "tiff":
            case "tif":
                return "image/tiff";
            case "dcm":
            case "dicom":
            case "dic":
            case "diconde":
                return "application/dicom";
            default:
                return "image/" + fileExtension.toLowerCase();
        }
    }
    
    /**
     * 判断是否为图片文件
     */
    private boolean isImageFile(String fileExtension) {
        return fileUploadProperties.getAllowedImageTypes().contains(fileExtension.toLowerCase());
    }
    
    /**
     * 删除文件
     * @param fileId 文件ID
     * @param projectId 项目ID
     * @param userId 用户ID
     * @return 删除是否成功
     */
    public boolean deleteFile(String fileId, String projectId, String userId) {
        try {
            // 1. 验证文件是否存在并且用户有权限访问
            Optional<File> fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
            if (!fileOpt.isPresent()) {
                throw new IllegalArgumentException("文件不存在或无权限访问");
            }
            
            File file = fileOpt.get();
            
            // 2. 从存储服务删除文件及其缩略图（忽略失败，避免影响数据库清理）
            deleteStoredObjectQuietly(file.getFilePath());
            deleteStoredObjectQuietly(file.getThumbnailPath());
            
            // 3. 从数据库删除记录
            fileRepository.delete(file);
            
            return true;
            
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("删除文件失败: " + e.getMessage(), e);
        }
    }

    private void deleteStoredObjectQuietly(String objectPath) {
        if (objectPath == null || objectPath.isBlank()) {
            return;
        }

        try {
            storageStrategy.delete(objectPath);
        } catch (Exception e) {
            logger.warn("删除存储对象失败，已忽略: path={}, reason={}", objectPath, e.getMessage());
        }
    }

    /**
     * 获取文件列表（分页）
     */
    public org.springframework.data.domain.Page<File> getFileList(String projectId, String userId, String directoryId, org.springframework.data.domain.Pageable pageable) {
        // 验证目录是否存在和权限
        directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(directoryId, projectId, userId, Directory.Status.ACTIVE)
            .orElseThrow(() -> new IllegalArgumentException("目录不存在或无权限访问"));
            
        return fileRepository.findByProjectIdAndUserIdAndDirectoryIdOrderByCreatedAtDesc(projectId, userId, directoryId, pageable);
    }
}
