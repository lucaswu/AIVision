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
        executor.setCorePoolSize(10);  // 核心线程数，支持默认并发数
        executor.setMaxPoolSize(50);   // 最大线程数
        executor.setQueueCapacity(200); // 队列容量
        executor.setThreadNamePrefix("File-Process-");
        executor.setKeepAliveSeconds(60);
        executor.initialize();
        return executor;
    }
} 