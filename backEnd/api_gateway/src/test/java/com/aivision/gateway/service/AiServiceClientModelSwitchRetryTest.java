package com.aivision.gateway.service;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.io.OutputStream;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.InetSocketAddress;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * model-agent 在模型发布切换时对 /inference/submit 返回 409 MODEL_SWITCH_IN_PROGRESS。
 * 这里用一个本地假 HTTP 服务模拟该窗口，验证 submitWithModelSwitchRetry 会退避重试
 * 而不是把第一次 409 直接当成任务失败抛出去。
 */
class AiServiceClientModelSwitchRetryTest {

    private HttpServer server;

    @AfterEach
    void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void submitRetriesOnModelSwitchInProgressThenSucceeds() throws Exception {
        AtomicInteger callCount = new AtomicInteger(0);
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/inference/submit", exchange -> {
            int n = callCount.incrementAndGet();
            int status;
            byte[] body;
            if (n < 3) {
                status = 409;
                body = "{\"detail\":\"MODEL_SWITCH_IN_PROGRESS: runtime set is switching\"}"
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8);
            } else {
                status = 202;
                body = "{\"task_id\":\"t1\",\"state\":\"pending\"}"
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8);
            }
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
        });
        server.start();
        int port = server.getAddress().getPort();

        AiServiceClient client = new AiServiceClient();
        setField(client, "inferenceServiceUrl", "http://127.0.0.1:" + port);
        Method initRestTemplate = AiServiceClient.class.getDeclaredMethod("initRestTemplate");
        initRestTemplate.setAccessible(true);
        initRestTemplate.invoke(client);

        Method submit = AiServiceClient.class.getDeclaredMethod("submitInferenceTask", String.class, List.class);
        submit.setAccessible(true);

        long start = System.currentTimeMillis();
        try {
            submit.invoke(client, "task-retry-test", List.of("a.jpg"));
        } catch (InvocationTargetException e) {
            throw new AssertionError("submit should have succeeded after retrying past 409s", e.getCause());
        }
        long elapsedMs = System.currentTimeMillis() - start;

        assertEquals(3, callCount.get(), "expected two 409 retries then a successful 3rd attempt");
        assertTrue(elapsedMs >= 2000, "expected at least one backoff wait (>=2s), took " + elapsedMs + "ms");
    }

    private static void setField(Object target, String name, Object value) throws Exception {
        Field f = AiServiceClient.class.getDeclaredField(name);
        f.setAccessible(true);
        f.set(target, value);
    }
}
