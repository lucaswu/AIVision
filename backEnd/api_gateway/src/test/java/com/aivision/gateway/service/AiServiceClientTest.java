package com.aivision.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
class AiServiceClientTest {

    @InjectMocks
    private AiServiceClient aiServiceClient;

    // 使用真实 ObjectMapper 进行解析测试
    @Spy
    private ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void testCallVisionAi_ReturnsMockData() {
        String taskId = "task-123";
        String filePath = "/some/path/image.jpg";

        // Act
        String resultJson = aiServiceClient.callVisionAi(filePath, taskId);

        // Assert
        assertNotNull(resultJson);
        assertTrue(resultJson.contains("metadata"), "Result should contain metadata");
        assertTrue(resultJson.contains("results"), "Result should contain results array");
        // Update: 'porosity' is mapped to 'E_round_defect' by postProcessVisionResult
        assertTrue(resultJson.contains("E_round_defect"), "Result should contain mapped defect 'E_round_defect'");
        
        // 验证 JSON 格式是否合法
        assertDoesNotThrow(() -> objectMapper.readTree(resultJson));
    }

    @Test
    void testCallVisionAi_PostProcessing() {
        String taskId = "task-123";
        String filePath = "test.jpg";

        // Act
        String resultJson = aiServiceClient.callVisionAi(filePath, taskId);

        try {
            JsonNode root = objectMapper.readTree(resultJson);
            // 验证 metadata 中的 total_defects 是否存在
            assertTrue(root.get("metadata").has("total_defects"));
            // 验证 results 数组不为空
            assertTrue(root.get("results").size() > 0);
        } catch (Exception e) {
            fail("JSON parsing failed: " + e.getMessage());
        }
    }
}

