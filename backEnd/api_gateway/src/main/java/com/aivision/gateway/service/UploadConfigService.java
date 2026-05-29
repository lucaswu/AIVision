package com.aivision.gateway.service;

import com.aivision.gateway.config.FileUploadProperties;
import com.aivision.gateway.model.UploadConfigResponse;
import java.util.ArrayList;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.unit.DataSize;

@Service
public class UploadConfigService {
    private static final Logger logger = LoggerFactory.getLogger(UploadConfigService.class);

    private final FileUploadProperties properties;

    public UploadConfigService(FileUploadProperties properties) {
        this.properties = properties;
    }

    public UploadConfigResponse getUploadConfig() {
        long maxFileSizeBytes = getMaxFileSizeBytes();
        long maxTotalSizeBytes = getMaxTotalSizeBytes();
        long batchMaxBytes = Math.min(
            parseSizeOrDefault(properties.getBatchMaxSize(), 500L * 1024 * 1024),
            maxTotalSizeBytes);
        int batchMaxFiles = positiveOrDefault(properties.getBatchMaxFiles(), 10);
        int batchTimeoutBaseMs = positiveOrDefault(properties.getBatchTimeoutBaseMs(), 60000);
        int batchTimeoutMsPerMB = positiveOrDefault(properties.getBatchTimeoutMsPerMB(), 1500);
        int maxRetries = Math.max(properties.getMaxRetries() == null ? 1 : properties.getMaxRetries(), 0);

        List<String> allowedTypes = properties.getAllowedImageTypes() == null
            ? List.of()
            : new ArrayList<>(properties.getAllowedImageTypes());

        return new UploadConfigResponse(
            maxFileSizeBytes,
            maxTotalSizeBytes,
            batchMaxFiles,
            batchMaxBytes,
            batchTimeoutBaseMs,
            batchTimeoutMsPerMB,
            maxRetries,
            allowedTypes);
    }

    public long getMaxFileSizeBytes() {
        return parseSizeOrDefault(properties.getMaxFileSize(), 200L * 1024 * 1024);
    }

    public long getMaxTotalSizeBytes() {
        return parseSizeOrDefault(properties.getMaxTotalSize(), 10L * 1024 * 1024 * 1024);
    }

    public String humanReadableSize(long bytes) {
        if (bytes >= 1024L * 1024 * 1024) {
            return (bytes / (1024L * 1024 * 1024)) + "GB";
        }
        if (bytes >= 1024L * 1024) {
            return (bytes / (1024L * 1024)) + "MB";
        }
        if (bytes >= 1024L) {
            return (bytes / 1024L) + "KB";
        }
        return bytes + "B";
    }

    public long parseSizeOrDefault(String value, long defaultBytes) {
        if (value == null || value.isBlank()) {
            return defaultBytes;
        }
        try {
            return DataSize.parse(value.trim()).toBytes();
        } catch (Exception e) {
            logger.warn("无法解析文件大小配置 '{}'，使用默认值 {} 字节", value, defaultBytes);
            return defaultBytes;
        }
    }

    private int positiveOrDefault(Integer value, int defaultValue) {
        return value == null || value <= 0 ? defaultValue : value;
    }
}
