package com.aivision.gateway.config;

import com.aivision.gateway.service.storage.LocalStorageStrategy;
import com.aivision.gateway.service.storage.MinioStorageStrategy;
import com.aivision.gateway.service.storage.StorageStrategy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class StorageConfig {

    private static final Logger logger = LoggerFactory.getLogger(StorageConfig.class);

    @Value("${storage.type:local}")
    private String storageType;

    @Value("${storage.local.base-dir:/app/data/files}")
    private String localBaseDir;

    @Value("${storage.minio.endpoint:http://localhost:9000}")
    private String minioEndpoint;

    @Value("${storage.minio.access-key:minioadmin}")
    private String minioAccessKey;

    @Value("${storage.minio.secret-key:minioadmin123}")
    private String minioSecretKey;

    @Value("${storage.minio.bucket:ai-vision-files}")
    private String minioBucket;

    @Bean
    public StorageStrategy storageStrategy() {
        if ("minio".equalsIgnoreCase(storageType)) {
            logger.info("Using MinIO Storage Strategy (Endpoint: {}, Bucket: {})", minioEndpoint, minioBucket);
            return new MinioStorageStrategy(minioEndpoint, minioAccessKey, minioSecretKey, minioBucket);
        } else {
            logger.info("Using Local Storage Strategy (BaseDir: {})", localBaseDir);
            return new LocalStorageStrategy(localBaseDir);
        }
    }
}
