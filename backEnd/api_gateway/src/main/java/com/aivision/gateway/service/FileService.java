package com.aivision.gateway.service;

import com.aivision.gateway.config.FileUploadProperties;
import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import org.apache.commons.io.FilenameUtils;
import org.apache.commons.io.IOUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.util.*;
import java.util.Base64;

@Service
@Transactional
public class FileService {
    
    @Autowired
    private FileRepository fileRepository;
    
    @Autowired
    private ProjectRepository projectRepository;
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private FileUploadProperties fileUploadProperties;
    
    @Value("${storage.local.base-dir:/data/files}")
    private String localBaseDir;
    
    // 本地根目录：/data/files/{projectId}/{userId}/{dirPath}/{storedName}
    
    /**
     * 上传多个文件
     */
    public FileUploadResponse uploadFiles(String projectId, String userId, String directoryId, MultipartFile[] files) {
        List<FileUploadResponse.SuccessFileInfo> successFiles = new ArrayList<>();
        List<FileUploadResponse.FailedFileInfo> failedFiles = new ArrayList<>();
        
        // 1. 验证基础参数
        if (!validateBasicParams(projectId, userId, directoryId, failedFiles)) {
            return new FileUploadResponse(0, failedFiles.size(), successFiles, failedFiles);
        }
        
        // 2. 获取目录信息
        Directory directory;
        try {
            directory = directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(
                directoryId, projectId, userId, Directory.Status.ACTIVE)
                .orElseThrow(() -> new IllegalArgumentException("目录不存在或无权限访问"));
        } catch (Exception e) {
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
        
        // 4. 逐个处理文件
        for (MultipartFile file : files) {
            try {
                processFile(file, projectId, userId, directoryId, directory, successFiles, failedFiles);
            } catch (Exception e) {
                failedFiles.add(new FileUploadResponse.FailedFileInfo(
                    file.getOriginalFilename(), "文件处理失败: " + e.getMessage()));
            }
        }
        
        return new FileUploadResponse(successFiles.size(), failedFiles.size(), successFiles, failedFiles);
    }
    
    /**
     * 验证基础参数
     */
    private boolean validateBasicParams(String projectId, String userId, String directoryId, 
                                       List<FileUploadResponse.FailedFileInfo> failedFiles) {
        // 验证项目是否存在并且属于当前用户
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "项目不存在"));
            return false;
        }
        
        // 验证项目是否属于当前用户
        if (!project.get().getOwnerId().equals(userId)) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "无权限访问该项目"));
            return false;
        }
        
        if (userId == null || userId.trim().isEmpty()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "用户ID不能为空"));
            return false;
        }
        
        if (directoryId == null || directoryId.trim().isEmpty()) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo("", "目录ID不能为空"));
            return false;
        }
        
        return true;
    }
    
    /**
     * 验证总文件大小
     */
    private boolean validateTotalSize(long totalSize, List<FileUploadResponse.FailedFileInfo> failedFiles, 
                                     MultipartFile[] files) {
        // 简单验证：10GB = 10 * 1024 * 1024 * 1024 bytes
        long maxTotalSizeBytes = 10L * 1024 * 1024 * 1024;
        
        if (totalSize > maxTotalSizeBytes) {
            for (MultipartFile file : files) {
                failedFiles.add(new FileUploadResponse.FailedFileInfo(
                    file.getOriginalFilename(), "总文件大小超过10GB限制"));
            }
            return false;
        }
        
        return true;
    }
    
    /**
     * 处理单个文件
     */
    private void processFile(MultipartFile file, String projectId, String userId, String directoryId,
                            Directory directory, List<FileUploadResponse.SuccessFileInfo> successFiles,
                            List<FileUploadResponse.FailedFileInfo> failedFiles) {
        
        String originalFilename = file.getOriginalFilename();
        
        try {
            // 1. 验证文件
            if (!validateFile(file, failedFiles)) {
                return;
            }
            
            // 2. 生成文件信息
            String fileId = UUID.randomUUID().toString();
            String fileExtension = FilenameUtils.getExtension(originalFilename).toLowerCase();
            String storedName = fileId + "." + fileExtension;
            String objectPath = buildObjectPath(projectId, userId, directory.getDirPath(), storedName);
            String fullPath = objectPath; // 直接使用相对路径，前缀由前端/服务拼接
            
            // 3. 保存到本地文件系统
            saveToLocal(file, objectPath);
            
            // 4. 保存到数据库
            File fileEntity = new File(
                fileId, projectId, userId, directoryId,
                originalFilename, storedName, fullPath,
                file.getSize(), file.getContentType(), fileExtension
            );
            
            fileRepository.save(fileEntity);
            
            // 5. 添加到成功列表
            successFiles.add(new FileUploadResponse.SuccessFileInfo(
                fileId, originalFilename, file.getSize(), fullPath));
                
        } catch (Exception e) {
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
        
        // 验证文件大小：200MB = 200 * 1024 * 1024 bytes
        long maxFileSizeBytes = 200L * 1024 * 1024;
        if (file.getSize() > maxFileSizeBytes) {
            failedFiles.add(new FileUploadResponse.FailedFileInfo(originalFilename, "文件大小超过200MB限制"));
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
     * 构建MinIO对象路径
     */
    private String buildObjectPath(String projectId, String userId, String dirPath, String storedName) {
        String normalizedDir = dirPath == null ? "" : dirPath;
        return String.format("/%s/%s%s/%s", projectId, userId, normalizedDir, storedName);
    }
    
    /**
     * 上传文件到MinIO
     */
    private void saveToLocal(MultipartFile file, String objectPath) throws Exception {
        String relative = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
        Path target = Path.of(localBaseDir).resolve(relative).normalize();
        Files.createDirectories(target.getParent());
        try (InputStream inputStream = file.getInputStream()) {
            Files.copy(inputStream, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }
    
    /**
     * 获取文件预览
     */
    public FilePreviewResponse getFilePreview(String fileId, String projectId, String userId) {
        // 1. 验证文件是否存在并且用户有权限访问
        Optional<File> fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
        if (!fileOpt.isPresent()) {
            throw new IllegalArgumentException("文件不存在或无权限访问");
        }
        
        File file = fileOpt.get();
        
        // 2. 验证是否为图片文件
        if (!isImageFile(file.getFileExtension())) {
            throw new IllegalArgumentException("该文件不是图片格式，无法预览");
        }
        
        try {
            // 3. 从本地获取文件数据
            String rel = file.getFilePath().startsWith("/") ? file.getFilePath().substring(1) : file.getFilePath();
            Path path = Path.of(localBaseDir).resolve(rel).normalize();
            InputStream inputStream = Files.newInputStream(path);
            
            // 4. 读取文件字节数据
            byte[] imageBytes = IOUtils.toByteArray(inputStream);
            inputStream.close();
            
            // 5. 获取图片尺寸信息
            Integer width = null;
            Integer height = null;
            try {
                ByteArrayInputStream bis = new ByteArrayInputStream(imageBytes);
                BufferedImage bufferedImage = ImageIO.read(bis);
                if (bufferedImage != null) {
                    width = bufferedImage.getWidth();
                    height = bufferedImage.getHeight();
                }
                bis.close();
            } catch (Exception e) {
                // 忽略尺寸获取失败，继续返回图片数据
            }
            
            // 6. 转换为Base64编码
            String base64Data = Base64.getEncoder().encodeToString(imageBytes);
            String mimeType = file.getMimeType() != null ? file.getMimeType() : "image/" + file.getFileExtension();
            String imageDataUrl = "data:" + mimeType + ";base64," + base64Data;
            
            // 7. 构建响应
            return new FilePreviewResponse(
                file.getFileId(),
                file.getOriginalName(),
                file.getFileSize(),
                mimeType,
                imageDataUrl,
                width,
                height
            );
            
        } catch (Exception e) {
            throw new RuntimeException("获取文件预览失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 获取文件图片数据 - 直接返回二进制数据
     */
    public FileImageData getFileImageData(String fileId, String projectId, String userId) {
        // 1. 验证文件是否存在并且用户有权限访问
        Optional<File> fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
        if (!fileOpt.isPresent()) {
            throw new IllegalArgumentException("文件不存在或无权限访问");
        }
        
        File file = fileOpt.get();
        
        // 2. 验证是否为图片文件
        if (!isImageFile(file.getFileExtension())) {
            throw new IllegalArgumentException("该文件不是图片格式，无法预览");
        }
        
        try {
            // 3. 从本地获取文件数据
            String rel = file.getFilePath().startsWith("/") ? file.getFilePath().substring(1) : file.getFilePath();
            Path path = Path.of(localBaseDir).resolve(rel).normalize();
            InputStream inputStream = Files.newInputStream(path);
            
            // 4. 读取文件字节数据
            byte[] imageBytes = IOUtils.toByteArray(inputStream);
            inputStream.close();
            
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
            
            // 2. 从本地删除文件（忽略失败）
            try {
                String rel = file.getFilePath().startsWith("/") ? file.getFilePath().substring(1) : file.getFilePath();
                Path path = Path.of(localBaseDir).resolve(rel).normalize();
                Files.deleteIfExists(path);
            } catch (Exception ignore) {}
            
            // 3. 从数据库删除记录
            fileRepository.delete(file);
            
            return true;
            
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("删除文件失败: " + e.getMessage(), e);
        }
    }
} 