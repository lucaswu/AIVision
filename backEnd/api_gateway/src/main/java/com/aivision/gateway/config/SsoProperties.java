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
    }
}
