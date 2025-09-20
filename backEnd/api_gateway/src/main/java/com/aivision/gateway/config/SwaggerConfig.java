package com.aivision.gateway.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {
    
    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("AI Vision API Gateway")
                        .description("AI Vision 检测系统的 API 网关服务\n\n" +
                                   "提供项目管理、任务处理、AI检测等核心功能的 REST API 接口。\n" +
                                   "支持缺陷检测、质量分析等多种 AI 视觉检测场景。\n\n" +
                                   "## 主要功能模块\n" +
                                   "- **项目管理**: 创建、查询、管理检测项目\n" +
                                   "- **任务处理**: 图像上传、AI检测任务管理\n" +
                                   "- **报告生成**: LLM智能分析报告生成\n" +
                                   "- **文件存储**: MinIO对象存储集成")
                        .version("1.0.0")
                        .contact(new Contact()
                                .name("AI Vision Team")
                                .url("https://github.com/your-org/ai-vision")
                                .email("support@aivision.com"))
                        .license(new License()
                                .name("MIT License")
                                .url("https://opensource.org/licenses/MIT"))
                );
    }
} 