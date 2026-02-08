package com.aivision.gateway.client;

import com.aivision.gateway.config.ThirdPartyProperties;
import com.aivision.gateway.model.thirdparty.ThirdPartyProjectResponse;
import com.aivision.gateway.model.thirdparty.ThirdPartyTokenResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;

@Component
public class ThirdPartyClient {

    private static final Logger logger = LoggerFactory.getLogger(ThirdPartyClient.class);

    private final ThirdPartyProperties properties;
    private final RestTemplate restTemplate;

    public ThirdPartyClient(ThirdPartyProperties properties) {
        this.properties = properties;
        this.restTemplate = new RestTemplate();
    }

    public String getAccessToken() {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", properties.getBasicAuth());
            headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

            MultiValueMap<String, String> map = new LinkedMultiValueMap<>();
            map.add("account", properties.getAccount());

            HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(map, headers);
            
            logger.info("Requesting access token from: {}", properties.getAuthUrl());
            logger.info("Auth Request Headers: {}", headers);
            logger.info("Auth Request Body: {}", map);

            ResponseEntity<ThirdPartyTokenResponse> response = restTemplate.postForEntity(
                    properties.getAuthUrl(),
                    request,
                    ThirdPartyTokenResponse.class
            );
            
            logger.info("Auth Response Code: {}", response.getStatusCode());
            logger.info("Auth Response Body: {}", response.getBody());

            if (response.getBody() != null && response.getBody().isSuccess() && response.getBody().getData() != null) {
                return response.getBody().getData().getToken();
            } else {
                logger.error("Failed to get access token: {}", response.getBody() != null ? response.getBody().getMsg() : "Empty response");
                return null;
            }
        } catch (Exception e) {
            logger.error("Error getting access token", e);
            return null;
        }
    }

    public ThirdPartyProjectResponse getProjects(String token) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", properties.getBasicAuth());
            headers.set("Blade-Auth", "bearer " + token);
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<String> request = new HttpEntity<>("{}", headers);

            logger.info("Requesting projects from: {}", properties.getProjectUrl());
            logger.info("Project Request Headers: {}", headers);

            ResponseEntity<ThirdPartyProjectResponse> response = restTemplate.postForEntity(
                    properties.getProjectUrl(),
                    request,
                    ThirdPartyProjectResponse.class
            );

            logger.info("Project Response Code: {}", response.getStatusCode());
            logger.info("Project Response Body: {}", response.getBody());

            return response.getBody();
        } catch (Exception e) {
            logger.error("Error getting projects", e);
            return null;
        }
    }
}
