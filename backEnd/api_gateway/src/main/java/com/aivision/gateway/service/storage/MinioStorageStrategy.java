package com.aivision.gateway.service.storage;

import io.minio.*;
import io.minio.errors.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;

public class MinioStorageStrategy implements StorageStrategy {

    private static final Logger logger = LoggerFactory.getLogger(MinioStorageStrategy.class);

    private final MinioClient minioClient;
    private final String bucketName;

    public MinioStorageStrategy(String endpoint, String accessKey, String secretKey, String bucketName) {
        this.minioClient = MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
        this.bucketName = bucketName;
        ensureBucketExists();
    }

    private void ensureBucketExists() {
        try {
            boolean found = minioClient.bucketExists(BucketExistsArgs.builder().bucket(bucketName).build());
            if (!found) {
                minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucketName).build());
                logger.info("Created MinIO bucket: {}", bucketName);
            }
        } catch (Exception e) {
            logger.error("Error checking/creating MinIO bucket: {}", e.getMessage());
            // Don't throw exception here to allow application startup even if MinIO is temporarily down
        }
    }

    @Override
    public void upload(InputStream inputStream, String objectPath, String contentType, long size) {
        try {
            String objectName = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(bucketName)
                            .object(objectName)
                            .stream(inputStream, size, -1)
                            .contentType(contentType)
                            .build());
            logger.info("Uploaded file to MinIO: {}/{}", bucketName, objectName);
        } catch (Exception e) {
            throw new RuntimeException("Failed to upload to MinIO: " + e.getMessage(), e);
        }
    }

    @Override
    public InputStream download(String objectPath) {
        try {
            String objectName = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            return minioClient.getObject(
                    GetObjectArgs.builder()
                            .bucket(bucketName)
                            .object(objectName)
                            .build());
        } catch (Exception e) {
            throw new RuntimeException("Failed to download from MinIO: " + e.getMessage(), e);
        }
    }

    @Override
    public void delete(String objectPath) {
        try {
            String objectName = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            minioClient.removeObject(
                    RemoveObjectArgs.builder()
                            .bucket(bucketName)
                            .object(objectName)
                            .build());
            logger.info("Deleted file from MinIO: {}/{}", bucketName, objectName);
        } catch (Exception e) {
            logger.warn("Failed to delete from MinIO: {}", e.getMessage());
        }
    }

    @Override
    public boolean exists(String objectPath) {
        try {
            String objectName = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            minioClient.statObject(
                    StatObjectArgs.builder()
                            .bucket(bucketName)
                            .object(objectName)
                            .build());
            return true;
        } catch (ErrorResponseException e) {
            if (e.errorResponse().code().equals("NoSuchKey")) {
                return false;
            }
            throw new RuntimeException("Error checking MinIO object existence: " + e.getMessage(), e);
        } catch (Exception e) {
            throw new RuntimeException("Error checking MinIO object existence: " + e.getMessage(), e);
        }
    }
}
