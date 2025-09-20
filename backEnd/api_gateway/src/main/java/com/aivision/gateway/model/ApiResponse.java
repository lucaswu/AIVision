package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class ApiResponse<T> {
    
    @JsonProperty("Code")
    private Integer code;
    
    @JsonProperty("Message") 
    private String message;
    
    @JsonProperty("Data")
    private T data;
    
    @JsonProperty("Total")
    private Integer total;
    
    // 构造函数
    public ApiResponse() {}
    
    public ApiResponse(Integer code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
    }
    
    public ApiResponse(Integer code, String message, T data, Integer total) {
        this.code = code;
        this.message = message;
        this.data = data;
        this.total = total;
    }
    
    // 静态方法创建成功响应
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(200, "操作成功", data);
    }
    
    public static <T> ApiResponse<T> success(String message, T data) {
        return new ApiResponse<>(200, message, data);
    }
    
    public static <T> ApiResponse<T> success(String message, T data, Integer total) {
        return new ApiResponse<>(200, message, data, total);
    }
    
    // 静态方法创建错误响应
    public static <T> ApiResponse<T> error(Integer code, String message) {
        return new ApiResponse<>(code, message, null);
    }
    
    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(500, message, null);
    }
    
    // Getters and Setters
    public Integer getCode() {
        return code;
    }
    
    public void setCode(Integer code) {
        this.code = code;
    }
    
    public String getMessage() {
        return message;
    }
    
    public void setMessage(String message) {
        this.message = message;
    }
    
    public T getData() {
        return data;
    }
    
    public void setData(T data) {
        this.data = data;
    }
    
    public Integer getTotal() {
        return total;
    }
    
    public void setTotal(Integer total) {
        this.total = total;
    }
} 