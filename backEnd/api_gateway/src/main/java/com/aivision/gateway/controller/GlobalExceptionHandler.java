package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.service.UploadConfigService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;

/**
 * 全局异常处理
 *
 * <p>multipart 解析阶段抛出的异常发生在进入 Controller 之前（DispatcherServlet.checkMultipart），
 * 因此无法被各 Controller 内部的 try/catch 捕获，默认会返回裸 500。这里统一拦截并返回结构化 JSON，
 * 前端可据此给出友好提示，而不是把整批上传当成未知错误。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @Autowired
    private UploadConfigService uploadConfigService;

    /**
     * 单个文件超过 max-file-size（默认 200MB）时由 Tomcat 在解析阶段抛出。
     * 注意：该异常一旦触发，整个 multipart 请求都会被拒绝（其余文件也无法保存），
     * 因此前端应在上传前过滤超大文件、并采用小批次上传以缩小影响范围。
     */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiResponse<Void>> handleMaxUploadSizeExceeded(MaxUploadSizeExceededException e) {
        logger.warn("上传被拒绝：存在超过大小限制的文件: {}", e.getMessage());
        String limitText = uploadConfigService.humanReadableSize(uploadConfigService.getMaxFileSizeBytes());
        return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE).body(
            ApiResponse.error(HttpStatus.PAYLOAD_TOO_LARGE.value(),
                "存在超过 " + limitText + " 的文件，已被拒绝；请压缩或拆分后重试"));
    }

    /**
     * 其它 multipart 解析异常（如请求体损坏、boundary 异常等），同样统一为结构化响应。
     */
    @ExceptionHandler(MultipartException.class)
    public ResponseEntity<ApiResponse<Void>> handleMultipartException(MultipartException e) {
        logger.warn("multipart 请求解析失败: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(
            ApiResponse.error(HttpStatus.BAD_REQUEST.value(), "上传请求解析失败，请重试"));
    }
}
