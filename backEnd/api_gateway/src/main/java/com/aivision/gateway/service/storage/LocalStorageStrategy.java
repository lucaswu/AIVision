package com.aivision.gateway.service.storage;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;

public class LocalStorageStrategy implements StorageStrategy {

    private static final Logger logger = LoggerFactory.getLogger(LocalStorageStrategy.class);

    private final String baseDir;

    public LocalStorageStrategy(String baseDir) {
        this.baseDir = baseDir;
    }

    @Override
    public void upload(InputStream inputStream, String objectPath, String contentType, long size) {
        try {
            String relative = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            Path target = Paths.get(baseDir).resolve(relative).normalize();
            Files.createDirectories(target.getParent());
            Files.copy(inputStream, target, StandardCopyOption.REPLACE_EXISTING);
            logger.info("Saved file to local: {}", target);
        } catch (IOException e) {
            throw new RuntimeException("Failed to save file locally: " + e.getMessage(), e);
        }
    }

    @Override
    public InputStream download(String objectPath) {
        try {
            String relative = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            Path target = Paths.get(baseDir).resolve(relative).normalize();
            if (!Files.exists(target)) {
                throw new RuntimeException("File not found locally: " + target);
            }
            return Files.newInputStream(target);
        } catch (IOException e) {
            throw new RuntimeException("Failed to read file locally: " + e.getMessage(), e);
        }
    }

    @Override
    public void delete(String objectPath) {
        try {
            String relative = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
            Path target = Paths.get(baseDir).resolve(relative).normalize();
            Files.deleteIfExists(target);
            logger.info("Deleted local file: {}", target);
        } catch (IOException e) {
            logger.warn("Failed to delete local file: {}", e.getMessage());
        }
    }

    @Override
    public boolean exists(String objectPath) {
        String relative = objectPath.startsWith("/") ? objectPath.substring(1) : objectPath;
        Path target = Paths.get(baseDir).resolve(relative).normalize();
        return Files.exists(target);
    }
}
