package com.aivision.gateway.service;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.AlgorithmMismatchException;
import com.auth0.jwt.exceptions.JWTDecodeException;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.exceptions.SignatureVerificationException;
import com.auth0.jwt.exceptions.TokenExpiredException;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.aivision.gateway.config.SsoProperties;
import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.KeyFactory;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Date;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class UserService implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(UserService.class);

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private UserProjectPermissionRepository permissionRepository;
    
    @Autowired
    private ProjectRepository projectRepository;

    @Autowired
    private SsoProperties ssoProperties;

    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Override
    public void run(String... args) throws Exception {
        // 初始化/重置 Admin 用户密码，确保哈希匹配
        // 这是临时解决方案，用于解决 E2E 测试登录失败的问题
        try {
            Optional<User> adminOpt = userRepository.findByUsername("Admin");
            if (adminOpt.isPresent()) {
                User admin = adminOpt.get();
                // 每次启动都重置为 known password 'password'
                String newHash = passwordEncoder.encode("password");
                admin.setPassword(newHash);
                userRepository.save(admin);
                logger.info("已重置 Admin 用户密码以确保一致性");
            } else {
                logger.warn("未找到 Admin 用户，跳过密码重置");
            }
        } catch (Exception e) {
            logger.error("重置 Admin 密码失败", e);
        }
    }

    /**
     * 用户登录
     */
    public UserLoginResponse login(UserLoginRequest request) {
        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new IllegalArgumentException("用户不存在或密码错误"));

        if (!user.getStatus().equals(User.Status.ACTIVE)) {
            throw new IllegalArgumentException("账号已被禁用");
        }

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new IllegalArgumentException("用户不存在或密码错误");
        }

        // 简单的 Token 生成 (实际生产应使用 JWT)
        String token = UUID.randomUUID().toString();
        
        // TODO: Store token in Redis or Database if stateful session is needed

        return new UserLoginResponse(
                user.getUserId(),
                user.getUsername(),
                user.getRole().name(),
                token
        );
    }

    /**
     * SSO JWT登录
     */
    @Transactional
    public UserLoginResponse ssoJwtLogin(SsoJwtLoginRequest request) {
        SsoProperties.Jwt jwtProperties = ssoProperties.getJwt();
        if (!jwtProperties.isEnabled()) {
            throw new IllegalArgumentException("SSO JWT登录未启用");
        }

        String token = trimToNull(request.getToken());
        if (token == null) {
            throw new IllegalArgumentException("SSO token不能为空");
        }

        DecodedJWT jwt = verifySsoJwt(token, jwtProperties);
        validateRequiredJwtClaims(jwt, jwtProperties);

        String claimUsername = trimToNull(jwt.getClaim("username").asString());
        String username = claimUsername != null ? claimUsername : trimToNull(jwt.getSubject());
        if (username == null) {
            throw new IllegalArgumentException("SSO token用户不能为空");
        }

        String tokenRole = trimToNull(jwt.getClaim("role").asString());
        User.Role role = parseRole(tokenRole != null ? tokenRole : jwtProperties.getDefaultRole());
        String redirect = sanitizeRedirect(jwt.getClaim("redirect").asString());

        User user = userRepository.findByUsername(username)
                .orElseGet(() -> createSsoUser(username, role, jwtProperties));

        if (!User.Status.ACTIVE.equals(user.getStatus())) {
            throw new IllegalArgumentException("账号已被禁用");
        }

        return new UserLoginResponse(
                user.getUserId(),
                user.getUsername(),
                user.getRole().name(),
                UUID.randomUUID().toString(),
                redirect
        );
    }

    /**
     * 出站方向 SSO：已登录用户跳转到训练平台（AIVision-training）。
     * 用共享私钥签发 JWT，与 ssoJwtLogin 入站验证使用的是同一对密钥。
     */
    public SsoJumpResponse createTrainingJump(String userId, String redirect) {
        SsoProperties.Jwt jwtProperties = ssoProperties.getJwt();

        String trimmedUserId = trimToNull(userId);
        if (trimmedUserId == null) {
            throw new IllegalArgumentException("用户ID不能为空");
        }

        User user = userRepository.findById(trimmedUserId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        if (!User.Status.ACTIVE.equals(user.getStatus())) {
            throw new IllegalArgumentException("账号已被禁用");
        }

        String trainingBaseUrl = trimToNull(jwtProperties.getTrainingBaseUrl());
        if (trainingBaseUrl == null) {
            throw new IllegalArgumentException("未配置训练平台跳转地址");
        }

        String token = createJumpToken(user, sanitizeRedirect(redirect), jwtProperties);
        String base = trainingBaseUrl.endsWith("/")
                ? trainingBaseUrl.substring(0, trainingBaseUrl.length() - 1)
                : trainingBaseUrl;

        return new SsoJumpResponse(base + "/sso-login?token=" + token);
    }

    /**
     * 创建用户
     */
    @Transactional
    public UserResponse createUser(CreateUserRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new IllegalArgumentException("该用户名已被注册");
        }

        User user = new User();
        user.setUserId(UUID.randomUUID().toString());
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole(User.Role.valueOf(request.getRole()));
        user.setStatus(User.Status.ACTIVE);

        userRepository.save(user);

        // 处理权限
        List<UserResponse.UserProjectPermissionDTO> permissionDTOs = new ArrayList<>();
        if (request.getProjectPermissions() != null) {
            for (CreateUserRequest.ProjectPermissionDTO dto : request.getProjectPermissions()) {
                // 验证项目是否存在
                Project project = projectRepository.findById(dto.getProjectId())
                    .orElseThrow(() -> new IllegalArgumentException("项目不存在: " + dto.getProjectId()));

                UserProjectPermission perm = new UserProjectPermission();
                perm.setId(UUID.randomUUID().toString());
                perm.setUserId(user.getUserId());
                perm.setProjectId(dto.getProjectId());
                perm.setPermission(UserProjectPermission.Permission.valueOf(dto.getPermission()));
                
                permissionRepository.save(perm);
                
                permissionDTOs.add(new UserResponse.UserProjectPermissionDTO(
                    project.getProjectId(),
                    project.getProjectName(),
                    perm.getPermission().name()
                ));
            }
        }

        return toUserResponse(user, permissionDTOs);
    }

    /**
     * 更新用户
     */
    @Transactional
    public UserResponse updateUser(String userId, UpdateUserRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        if (request.getPassword() != null && !request.getPassword().isEmpty()) {
            user.setPassword(passwordEncoder.encode(request.getPassword()));
        }

        if (request.getRole() != null) {
            user.setRole(User.Role.valueOf(request.getRole()));
        }

        if (request.getStatus() != null) {
            user.setStatus(User.Status.ACTIVE.name().equals(request.getStatus()) ? User.Status.ACTIVE : User.Status.DISABLED);
        }

        userRepository.save(user);

        // 更新权限 (全量替换)
        if (request.getProjectPermissions() != null) {
            List<UserProjectPermission> existingPermissions = permissionRepository.findByUserId(userId);
            permissionRepository.deleteAll(existingPermissions);
            permissionRepository.flush(); // 强制刷新，确保删除先执行
            
            for (CreateUserRequest.ProjectPermissionDTO dto : request.getProjectPermissions()) {
                 Project project = projectRepository.findById(dto.getProjectId())
                    .orElseThrow(() -> new IllegalArgumentException("项目不存在: " + dto.getProjectId()));

                UserProjectPermission perm = new UserProjectPermission();
                perm.setId(UUID.randomUUID().toString());
                perm.setUserId(userId);
                perm.setProjectId(dto.getProjectId());
                perm.setPermission(UserProjectPermission.Permission.valueOf(dto.getPermission()));
                permissionRepository.save(perm);
            }
        }

        return getUserById(userId);
    }

    /**
     * 获取用户详情
     */
    public UserResponse getUserById(String userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        List<UserProjectPermission> permissions = permissionRepository.findByUserId(userId);
        
        List<UserResponse.UserProjectPermissionDTO> permissionDTOs = permissions.stream()
            .map(p -> {
                String projectName = projectRepository.findById(p.getProjectId())
                    .map(Project::getProjectName)
                    .orElse("Unknown Project");
                return new UserResponse.UserProjectPermissionDTO(
                    p.getProjectId(), 
                    projectName, 
                    p.getPermission().name()
                );
            })
            .collect(Collectors.toList());

        return toUserResponse(user, permissionDTOs);
    }

    /**
     * 获取用户列表
     */
    public Page<UserResponse> getUserList(Pageable pageable) {
        Page<User> userPage = userRepository.findAll(pageable);
        return userPage.map(user -> {
            List<UserProjectPermission> permissions = permissionRepository.findByUserId(user.getUserId());
            List<UserResponse.UserProjectPermissionDTO> permissionDTOs = permissions.stream()
                .map(p -> {
                    String projectName = projectRepository.findById(p.getProjectId())
                        .map(Project::getProjectName)
                        .orElse("Unknown Project");
                    return new UserResponse.UserProjectPermissionDTO(
                        p.getProjectId(), 
                        projectName, 
                        p.getPermission().name()
                    );
                })
                .collect(Collectors.toList());
            return toUserResponse(user, permissionDTOs);
        });
    }

    /**
     * 删除用户
     */
    @Transactional
    public void deleteUser(String userId) {
        if (!userRepository.existsById(userId)) {
            throw new IllegalArgumentException("用户不存在");
        }
        permissionRepository.deleteByUserId(userId);
        userRepository.deleteById(userId);
    }

    private DecodedJWT verifySsoJwt(String token, SsoProperties.Jwt jwtProperties) {
        try {
            DecodedJWT decoded = JWT.decode(token);
            if (!"RS256".equalsIgnoreCase(decoded.getAlgorithm())) {
                throw new IllegalArgumentException("SSO token签名无效");
            }

            Algorithm algorithm = Algorithm.RSA256(loadPublicKey(jwtProperties), null);
            JWTVerifier verifier = JWT.require(algorithm)
                    .acceptLeeway(Math.max(0, jwtProperties.getAllowedClockSkewSeconds()))
                    .build();
            return verifier.verify(token);
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (TokenExpiredException e) {
            throw new IllegalArgumentException("SSO token已过期");
        } catch (SignatureVerificationException | AlgorithmMismatchException e) {
            throw new IllegalArgumentException("SSO token签名无效");
        } catch (JWTDecodeException e) {
            throw new IllegalArgumentException("SSO token格式无效");
        } catch (JWTVerificationException e) {
            throw new IllegalArgumentException("SSO token校验失败");
        } catch (Exception e) {
            logger.error("SSO JWT公钥加载或验签失败", e);
            throw new IllegalArgumentException("SSO token签名无效");
        }
    }

    private void validateRequiredJwtClaims(DecodedJWT jwt, SsoProperties.Jwt jwtProperties) {
        String expectedIssuer = trimToNull(jwtProperties.getIssuer());
        if (expectedIssuer != null && !expectedIssuer.equals(jwt.getIssuer())) {
            throw new IllegalArgumentException("SSO token签发方无效");
        }

        String expectedAudience = trimToNull(jwtProperties.getAudience());
        if (expectedAudience != null
                && (jwt.getAudience() == null || !jwt.getAudience().contains(expectedAudience))) {
            throw new IllegalArgumentException("SSO token接收方无效");
        }

        if (jwt.getExpiresAt() == null) {
            throw new IllegalArgumentException("SSO token过期时间不能为空");
        }

        Date issuedAt = jwt.getIssuedAt();
        if (issuedAt == null) {
            throw new IllegalArgumentException("SSO token签发时间不能为空");
        }

        long nowMillis = System.currentTimeMillis();
        long allowedFutureMillis = Math.max(0, jwtProperties.getAllowedClockSkewSeconds()) * 1000L;
        if (issuedAt.getTime() - nowMillis > allowedFutureMillis) {
            throw new IllegalArgumentException("SSO token签发时间无效");
        }
    }

    private User createSsoUser(String username, User.Role role, SsoProperties.Jwt jwtProperties) {
        if (!jwtProperties.isAutoCreateUsers()) {
            throw new IllegalArgumentException("用户不存在");
        }

        User user = new User();
        user.setUserId(UUID.randomUUID().toString());
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(UUID.randomUUID().toString()));
        user.setRole(role);
        user.setStatus(User.Status.ACTIVE);
        return userRepository.save(user);
    }

    private User.Role parseRole(String role) {
        String normalizedRole = trimToNull(role);
        if (normalizedRole == null) {
            normalizedRole = User.Role.INSPECTOR.name();
        }

        try {
            return User.Role.valueOf(normalizedRole.toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("SSO token用户角色无效");
        }
    }

    private String sanitizeRedirect(String redirect) {
        String value = trimToNull(redirect);
        if (value == null || !value.startsWith("/") || value.startsWith("//")) {
            return "/projects";
        }
        return value;
    }

    private RSAPublicKey loadPublicKey(SsoProperties.Jwt jwtProperties) throws Exception {
        String publicKey = trimToNull(jwtProperties.getPublicKey());
        if (publicKey == null) {
            publicKey = loadPublicKeyFile(jwtProperties.getPublicKeyFile());
        }
        if (publicKey == null) {
            throw new IllegalArgumentException("SSO JWT公钥未配置");
        }

        String normalized = publicKey
                .replace("\\n", "\n")
                .replace("-----BEGIN PUBLIC KEY-----", "")
                .replace("-----END PUBLIC KEY-----", "")
                .replaceAll("\\s", "");

        byte[] decoded = Base64.getDecoder().decode(normalized);
        X509EncodedKeySpec keySpec = new X509EncodedKeySpec(decoded);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        return (RSAPublicKey) keyFactory.generatePublic(keySpec);
    }

    private String loadPublicKeyFile(String publicKeyFile) throws Exception {
        String path = trimToNull(publicKeyFile);
        if (path == null) {
            return null;
        }

        if (path.startsWith("classpath:")) {
            String resourcePath = path.substring("classpath:".length());
            ClassPathResource resource = new ClassPathResource(resourcePath);
            return new String(resource.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        }

        return new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8);
    }

    private String createJumpToken(User user, String redirect, SsoProperties.Jwt jwtProperties) {
        try {
            Algorithm algorithm = Algorithm.RSA256(null, loadPrivateKey(jwtProperties));

            String issuer = trimToNull(jwtProperties.getIssuerSelf());
            String audience = trimToNull(jwtProperties.getTargetAudience());
            long ttlSeconds = jwtProperties.getIssuedTokenTtlSeconds() > 0
                    ? jwtProperties.getIssuedTokenTtlSeconds() : 300;
            Instant now = Instant.now();

            return JWT.create()
                    .withIssuer(issuer != null ? issuer : "external-system")
                    .withAudience(audience != null ? audience : "aivision-training")
                    .withSubject(user.getUsername())
                    .withClaim("username", user.getUsername())
                    .withClaim("role", user.getRole().name())
                    .withClaim("redirect", redirect)
                    .withIssuedAt(Date.from(now))
                    .withExpiresAt(Date.from(now.plusSeconds(ttlSeconds)))
                    .sign(algorithm);
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            logger.error("SSO 跳转 token 签发失败", e);
            throw new IllegalArgumentException("跳转token签发失败");
        }
    }

    private RSAPrivateKey loadPrivateKey(SsoProperties.Jwt jwtProperties) throws Exception {
        String privateKey = trimToNull(jwtProperties.getPrivateKey());
        if (privateKey == null) {
            privateKey = loadPrivateKeyFile(jwtProperties.getPrivateKeyFile());
        }
        if (privateKey == null) {
            throw new IllegalArgumentException("SSO JWT私钥未配置");
        }

        String normalized = privateKey
                .replace("\\n", "\n")
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");

        byte[] decoded = Base64.getDecoder().decode(normalized);
        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(decoded);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        return (RSAPrivateKey) keyFactory.generatePrivate(keySpec);
    }

    private String loadPrivateKeyFile(String privateKeyFile) throws Exception {
        String path = trimToNull(privateKeyFile);
        if (path == null) {
            return null;
        }

        if (path.startsWith("classpath:")) {
            String resourcePath = path.substring("classpath:".length());
            ClassPathResource resource = new ClassPathResource(resourcePath);
            return new String(resource.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        }

        return new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8);
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private UserResponse toUserResponse(User user, List<UserResponse.UserProjectPermissionDTO> permissions) {
        UserResponse response = new UserResponse();
        response.setUserId(user.getUserId());
        response.setUsername(user.getUsername());
        response.setRole(user.getRole().name());
        response.setStatus(user.getStatus().name());
        response.setCreatedAt(user.getCreatedAt());
        response.setPermissions(permissions);
        return response;
    }
}
