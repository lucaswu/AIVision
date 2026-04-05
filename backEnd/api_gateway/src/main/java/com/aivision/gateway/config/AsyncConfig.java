package com.aivision.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
@EnableAsync
public class AsyncConfig {
    
    /**
     * AI任务处理线程池
     */
    @Bean("aiTaskExecutor")
    public Executor aiTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);  // 核心线程数
        executor.setMaxPoolSize(20);  // 最大线程数
        executor.setQueueCapacity(100); // 队列容量
        executor.setThreadNamePrefix("AI-Task-");
        executor.setKeepAliveSeconds(60);
        executor.initialize();
        return executor;
    }
    
    /**
     * 文件处理线程池
     */
    @Bean("fileProcessExecutor") 
    public Executor fileProcessExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(200);
        executor.setThreadNamePrefix("File-Process-");
        executor.setKeepAliveSeconds(60);
        executor.initialize();
        return executor;
    }

    /**
     * 缩略图生成线程池
     * - 核心 2 线程：一般情况下足够，不抢占主业务资源
     * - 最大 4 线程：突发批量上传时可弹性扩展
     * - 队列 200：队满时静默丢弃（DiscardPolicy），不影响上传主流程
     */
    @Bean("thumbnailExecutor")
    public Executor thumbnailExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(2);
        executor.setMaxPoolSize(4);
        executor.setQueueCapacity(200);
        executor.setThreadNamePrefix("thumbnail-");
        executor.setRejectedExecutionHandler(new java.util.concurrent.ThreadPoolExecutor.DiscardPolicy());
        executor.initialize();
        return executor;
    }
} 