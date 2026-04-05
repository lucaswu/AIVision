package com.aivision.gateway.service;

import com.aivision.gateway.model.File;
import com.aivision.gateway.model.User;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.MemoryCacheImageOutputStream;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Iterator;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/**
 * 缩略图生成与读取服务
 *
 * <p>负责将 BMP 原图异步压缩为 JPEG（质量 85%）并存回 Storage，
 * 生成成功后更新 file.thumbnail_path。
 *
 * <p>原始 BMP 文件完全不受影响，JPEG 仅作为视觉加速层。
 */
@Service
public class ThumbnailService {

    private static final Logger logger = LoggerFactory.getLogger(ThumbnailService.class);

    /** JPEG 压缩质量，0.0~1.0 */
    private static final float JPEG_QUALITY = 0.85f;

    @Autowired
    private StorageStrategy storageStrategy;

    @Autowired
    private FileRepository fileRepository;

    @Autowired
    private UserRepository userRepository;

    // ──────────────────────────────────────────────────────────────────────────
    // 异步生成缩略图（上传后触发）
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * 异步为指定文件生成 JPEG 缩略图。
     * 在独立线程池（thumbnailExecutor）中执行，不阻塞上传响应。
     * 失败时静默记录日志，不抛出异常。
     *
     * @param fileId 需要生成缩略图的文件 ID
     */
    @Async("thumbnailExecutor")
    public CompletableFuture<Void> generateAndStore(String fileId) {
        try {
            Optional<File> fileOpt = fileRepository.findById(fileId);
            if (fileOpt.isEmpty()) {
                logger.warn("ThumbnailService: 文件不存在, fileId={}", fileId);
                return CompletableFuture.completedFuture(null);
            }

            File file = fileOpt.get();

            // 已存在缩略图则跳过（幂等）
            if (file.getThumbnailPath() != null && !file.getThumbnailPath().isBlank()) {
                logger.debug("ThumbnailService: 缩略图已存在, fileId={}", fileId);
                return CompletableFuture.completedFuture(null);
            }

            // 1. 读取原始 BMP 数据
            byte[] originalBytes;
            try (InputStream is = storageStrategy.download(file.getFilePath())) {
                originalBytes = is.readAllBytes();
            }

            // 2. 解码 BMP → BufferedImage
            BufferedImage image = ImageIO.read(new ByteArrayInputStream(originalBytes));
            if (image == null) {
                logger.warn("ThumbnailService: 无法解码图像, fileId={}, path={}", fileId, file.getFilePath());
                return CompletableFuture.completedFuture(null);
            }

            // 3. 若图像带 Alpha 通道（如 ARGB），转换为 RGB（JPEG 不支持 alpha）
            BufferedImage rgbImage = image;
            if (image.getType() != BufferedImage.TYPE_INT_RGB &&
                image.getType() != BufferedImage.TYPE_3BYTE_BGR) {
                rgbImage = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
                rgbImage.createGraphics().drawImage(image, 0, 0, null);
            }

            // 4. 编码为 JPEG Q85
            byte[] jpegBytes = encodeJpeg(rgbImage, JPEG_QUALITY);

            // 5. JPEG 存储路径约定：原路径 + ".thumb.jpg"
            String thumbPath = file.getFilePath() + ".thumb.jpg";

            // 6. 上传到 Storage
            storageStrategy.upload(
                new ByteArrayInputStream(jpegBytes),
                thumbPath,
                "image/jpeg",
                jpegBytes.length
            );

            // 7. 持久化 thumbnail_path
            file.setThumbnailPath(thumbPath);
            fileRepository.save(file);

            logger.info("ThumbnailService: 缩略图生成成功, fileId={}, thumbPath={}, 原大小={}KB → 缩略图={}KB",
                fileId, thumbPath,
                originalBytes.length / 1024,
                jpegBytes.length / 1024);

        } catch (Exception e) {
            // 缩略图生成失败不影响正常使用，静默记录
            logger.warn("ThumbnailService: 缩略图生成失败, fileId={}, 原因={}", fileId, e.getMessage());
        }

        return CompletableFuture.completedFuture(null);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 读取缩略图（Controller 调用）
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * 获取指定文件的 JPEG 缩略图字节。
     *
     * @param fileId    文件 ID
     * @param projectId 项目 ID（用于权限校验）
     * @param userId    用户 ID（用于权限校验）
     * @return JPEG 字节数组；缩略图尚未就绪（thumbnail_path 为 null）时返回 null
     * @throws IllegalArgumentException 文件不存在或无权限访问
     */
    public byte[] getThumbnailBytes(String fileId, String projectId, String userId) {
        // 1. 权限校验（复用与 previewFile 相同的逻辑）
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        Optional<File> fileOpt;
        if (user.getRole() == User.Role.ADMIN) {
            fileOpt = fileRepository.findByFileIdAndProjectId(fileId, projectId);
        } else {
            fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
        }

        File file = fileOpt.orElseThrow(() -> new IllegalArgumentException("文件不存在或无权限访问"));

        // 2. 检查缩略图是否就绪
        String thumbPath = file.getThumbnailPath();
        if (thumbPath == null || thumbPath.isBlank()) {
            return null; // 调用方返回 404
        }

        // 3. 读取 JPEG 字节
        try (InputStream is = storageStrategy.download(thumbPath)) {
            return is.readAllBytes();
        } catch (Exception e) {
            logger.warn("ThumbnailService: 读取缩略图失败, fileId={}, thumbPath={}, 原因={}", fileId, thumbPath, e.getMessage());
            return null; // 读取失败也返回 null，触发前端回退
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 内部工具方法
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * 将 BufferedImage 编码为 JPEG 字节数组。
     */
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
}
