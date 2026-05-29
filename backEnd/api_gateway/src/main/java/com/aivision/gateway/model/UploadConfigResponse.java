package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class UploadConfigResponse {
    @JsonProperty("MaxFileSizeBytes")
    private long maxFileSizeBytes;

    @JsonProperty("MaxTotalSizeBytes")
    private long maxTotalSizeBytes;

    @JsonProperty("BatchMaxFiles")
    private int batchMaxFiles;

    @JsonProperty("BatchMaxBytes")
    private long batchMaxBytes;

    @JsonProperty("BatchTimeoutBaseMs")
    private int batchTimeoutBaseMs;

    @JsonProperty("BatchTimeoutMsPerMB")
    private int batchTimeoutMsPerMB;

    @JsonProperty("MaxRetries")
    private int maxRetries;

    @JsonProperty("AllowedImageTypes")
    private List<String> allowedImageTypes;

    public UploadConfigResponse(
            long maxFileSizeBytes,
            long maxTotalSizeBytes,
            int batchMaxFiles,
            long batchMaxBytes,
            int batchTimeoutBaseMs,
            int batchTimeoutMsPerMB,
            int maxRetries,
            List<String> allowedImageTypes) {
        this.maxFileSizeBytes = maxFileSizeBytes;
        this.maxTotalSizeBytes = maxTotalSizeBytes;
        this.batchMaxFiles = batchMaxFiles;
        this.batchMaxBytes = batchMaxBytes;
        this.batchTimeoutBaseMs = batchTimeoutBaseMs;
        this.batchTimeoutMsPerMB = batchTimeoutMsPerMB;
        this.maxRetries = maxRetries;
        this.allowedImageTypes = allowedImageTypes;
    }

    public long getMaxFileSizeBytes() {
        return maxFileSizeBytes;
    }

    public long getMaxTotalSizeBytes() {
        return maxTotalSizeBytes;
    }

    public int getBatchMaxFiles() {
        return batchMaxFiles;
    }

    public long getBatchMaxBytes() {
        return batchMaxBytes;
    }

    public int getBatchTimeoutBaseMs() {
        return batchTimeoutBaseMs;
    }

    public int getBatchTimeoutMsPerMB() {
        return batchTimeoutMsPerMB;
    }

    public int getMaxRetries() {
        return maxRetries;
    }

    public List<String> getAllowedImageTypes() {
        return allowedImageTypes;
    }
}
