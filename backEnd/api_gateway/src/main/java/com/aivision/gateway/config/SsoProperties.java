package com.aivision.gateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "sso")
public class SsoProperties {
    private Jwt jwt = new Jwt();

    public Jwt getJwt() {
        return jwt;
    }

    public void setJwt(Jwt jwt) {
        this.jwt = jwt;
    }

    public static class Jwt {
        private boolean enabled = false;
        private String publicKey;
        private String publicKeyFile;
        private String issuer = "external-system";
        private String audience = "ai-vision";
        private long allowedClockSkewSeconds = 60;
        private boolean autoCreateUsers = true;
        private String defaultRole = "INSPECTOR";

        // 出站方向：用共享私钥签发 token，供已登录用户跳转到训练平台（AIVision-training）
        private String privateKey;
        private String privateKeyFile = "classpath:sso_private_key.pem";
        private String issuerSelf = "external-system";
        private String targetAudience = "aivision-training";
        private String trainingBaseUrl;
        private long issuedTokenTtlSeconds = 300;

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public String getPublicKey() {
            return publicKey;
        }

        public void setPublicKey(String publicKey) {
            this.publicKey = publicKey;
        }

        public String getPublicKeyFile() {
            return publicKeyFile;
        }

        public void setPublicKeyFile(String publicKeyFile) {
            this.publicKeyFile = publicKeyFile;
        }

        public String getIssuer() {
            return issuer;
        }

        public void setIssuer(String issuer) {
            this.issuer = issuer;
        }

        public String getAudience() {
            return audience;
        }

        public void setAudience(String audience) {
            this.audience = audience;
        }

        public long getAllowedClockSkewSeconds() {
            return allowedClockSkewSeconds;
        }

        public void setAllowedClockSkewSeconds(long allowedClockSkewSeconds) {
            this.allowedClockSkewSeconds = allowedClockSkewSeconds;
        }

        public boolean isAutoCreateUsers() {
            return autoCreateUsers;
        }

        public void setAutoCreateUsers(boolean autoCreateUsers) {
            this.autoCreateUsers = autoCreateUsers;
        }

        public String getDefaultRole() {
            return defaultRole;
        }

        public void setDefaultRole(String defaultRole) {
            this.defaultRole = defaultRole;
        }

        public String getPrivateKey() {
            return privateKey;
        }

        public void setPrivateKey(String privateKey) {
            this.privateKey = privateKey;
        }

        public String getPrivateKeyFile() {
            return privateKeyFile;
        }

        public void setPrivateKeyFile(String privateKeyFile) {
            this.privateKeyFile = privateKeyFile;
        }

        public String getIssuerSelf() {
            return issuerSelf;
        }

        public void setIssuerSelf(String issuerSelf) {
            this.issuerSelf = issuerSelf;
        }

        public String getTargetAudience() {
            return targetAudience;
        }

        public void setTargetAudience(String targetAudience) {
            this.targetAudience = targetAudience;
        }

        public String getTrainingBaseUrl() {
            return trainingBaseUrl;
        }

        public void setTrainingBaseUrl(String trainingBaseUrl) {
            this.trainingBaseUrl = trainingBaseUrl;
        }

        public long getIssuedTokenTtlSeconds() {
            return issuedTokenTtlSeconds;
        }

        public void setIssuedTokenTtlSeconds(long issuedTokenTtlSeconds) {
            this.issuedTokenTtlSeconds = issuedTokenTtlSeconds;
        }
    }
}
