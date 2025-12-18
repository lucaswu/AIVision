package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class UserService {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private UserProjectPermissionRepository permissionRepository;
    
    @Autowired
    private ProjectRepository projectRepository;

    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

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
            permissionRepository.deleteByUserId(userId);
            
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
    public Page<User> getUserList(Pageable pageable) {
        return userRepository.findAll(pageable);
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

