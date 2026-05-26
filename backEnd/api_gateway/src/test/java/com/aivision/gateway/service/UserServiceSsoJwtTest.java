package com.aivision.gateway.service;

import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import com.aivision.gateway.config.SsoProperties;
import com.aivision.gateway.model.SsoJwtLoginRequest;
import com.aivision.gateway.model.User;
import com.aivision.gateway.model.UserLoginResponse;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class UserServiceSsoJwtTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private UserProjectPermissionRepository permissionRepository;

    @Mock
    private ProjectRepository projectRepository;

    @InjectMocks
    private UserService userService;

    private RSAPrivateKey privateKey;

    @BeforeEach
    void setUp() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        KeyPair keyPair = generator.generateKeyPair();

        privateKey = (RSAPrivateKey) keyPair.getPrivate();
        RSAPublicKey publicKey = (RSAPublicKey) keyPair.getPublic();

        SsoProperties properties = new SsoProperties();
        SsoProperties.Jwt jwt = properties.getJwt();
        jwt.setEnabled(true);
        jwt.setPublicKey(toPem(publicKey));
        jwt.setIssuer("external-system");
        jwt.setAudience("ai-vision");
        jwt.setAllowedClockSkewSeconds(60);
        jwt.setAutoCreateUsers(true);
        jwt.setDefaultRole("INSPECTOR");

        ReflectionTestUtils.setField(userService, "ssoProperties", properties);
    }

    @Test
    void ssoJwtLogin_ShouldCreateUserAndReturnRedirect() {
        when(userRepository.findByUsername("sso-user")).thenReturn(Optional.empty());
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

        SsoJwtLoginRequest request = new SsoJwtLoginRequest();
        request.setToken(createToken("external-system", "ai-vision", "sso-user", "ADMIN", "/projects/123/files"));

        UserLoginResponse response = userService.ssoJwtLogin(request);

        assertEquals("sso-user", response.getUsername());
        assertEquals("ADMIN", response.getRole());
        assertEquals("/projects/123/files", response.getRedirect());
        assertNotNull(response.getToken());

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        org.mockito.Mockito.verify(userRepository).save(userCaptor.capture());
        assertEquals(User.Status.ACTIVE, userCaptor.getValue().getStatus());
        assertEquals(User.Role.ADMIN, userCaptor.getValue().getRole());
    }

    @Test
    void ssoJwtLogin_ShouldKeepExistingUserRoleAndSanitizeRedirect() {
        User existing = new User();
        existing.setUserId("user-1");
        existing.setUsername("sso-user");
        existing.setPassword("not-used");
        existing.setRole(User.Role.INSPECTOR);
        existing.setStatus(User.Status.ACTIVE);

        when(userRepository.findByUsername("sso-user")).thenReturn(Optional.of(existing));

        SsoJwtLoginRequest request = new SsoJwtLoginRequest();
        request.setToken(createToken("external-system", "ai-vision", "sso-user", "ADMIN", "https://example.com"));

        UserLoginResponse response = userService.ssoJwtLogin(request);

        assertEquals("user-1", response.getUserId());
        assertEquals("INSPECTOR", response.getRole());
        assertEquals("/projects", response.getRedirect());
    }

    @Test
    void ssoJwtLogin_ShouldRejectInvalidIssuer() {
        SsoJwtLoginRequest request = new SsoJwtLoginRequest();
        request.setToken(createToken("other-system", "ai-vision", "sso-user", "INSPECTOR", "/projects"));

        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> userService.ssoJwtLogin(request)
        );
        assertEquals("SSO token签发方无效", exception.getMessage());
    }

    private String createToken(String issuer, String audience, String username, String role, String redirect) {
        Instant now = Instant.now();
        return JWT.create()
                .withIssuer(issuer)
                .withAudience(audience)
                .withSubject(username)
                .withClaim("username", username)
                .withClaim("role", role)
                .withClaim("redirect", redirect)
                .withIssuedAt(Date.from(now))
                .withExpiresAt(Date.from(now.plusSeconds(300)))
                .sign(Algorithm.RSA256(null, privateKey));
    }

    private String toPem(RSAPublicKey publicKey) {
        String encoded = Base64.getMimeEncoder(64, "\n".getBytes())
                .encodeToString(publicKey.getEncoded());
        return "-----BEGIN PUBLIC KEY-----\n" + encoded + "\n-----END PUBLIC KEY-----";
    }
}
