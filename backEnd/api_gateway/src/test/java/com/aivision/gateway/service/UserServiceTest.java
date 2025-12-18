package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Collections;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private UserProjectPermissionRepository permissionRepository;

    @Mock
    private ProjectRepository projectRepository;

    @InjectMocks
    private UserService userService;

    // Reflection is needed to inject the real encoder or spy, 
    // but since the service instantiates it directly (private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();),
    // we should test it with the real encoder or refactor the service to allow injection.
    // For this test, we will assume the real BCrypt works (it's a library), 
    // and just verify logic. The real encoder will run.

    @Test
    void testCreateUser_Success() {
        // Arrange
        CreateUserRequest request = new CreateUserRequest();
        request.setUsername("testuser");
        request.setPassword("password123");
        request.setRole("INSPECTOR");
        
        when(userRepository.existsByUsername(anyString())).thenReturn(false);
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

        // Act
        UserResponse response = userService.createUser(request);

        // Assert
        assertNotNull(response.getUserId());
        assertEquals("testuser", response.getUsername());
        assertEquals("INSPECTOR", response.getRole());
        
        verify(userRepository, times(1)).save(any(User.class));
    }

    @Test
    void testCreateUser_DuplicateUsername() {
        // Arrange
        CreateUserRequest request = new CreateUserRequest();
        request.setUsername("testuser");
        request.setPassword("password123");
        
        when(userRepository.existsByUsername("testuser")).thenReturn(true);

        // Act & Assert
        assertThrows(IllegalArgumentException.class, () -> userService.createUser(request));
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void testLogin_Success() {
        // Arrange
        String rawPassword = "password123";
        // Since we can't easily mock the internal PasswordEncoder of the service without refactoring,
        // we have to rely on knowing how it encodes? No, we rely on the Service hashing it during creation.
        // But here we are mocking the findByEmail, so we need to return a User with a HASHED password that matches.
        
        // Let's manually create a hash that matches "password123" using a real encoder for the mock data
        org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder encoder = new org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder();
        String hashedPassword = encoder.encode(rawPassword);

        User mockUser = new User();
        mockUser.setUserId("user-1");
        mockUser.setUsername("testuser");
        mockUser.setPassword(hashedPassword);
        mockUser.setRole(User.Role.ADMIN);
        mockUser.setStatus(User.Status.ACTIVE);

        when(userRepository.findByUsername("testuser")).thenReturn(Optional.of(mockUser));

        UserLoginRequest loginRequest = new UserLoginRequest();
        loginRequest.setUsername("testuser");
        loginRequest.setPassword(rawPassword);

        // Act
        UserLoginResponse response = userService.login(loginRequest);

        // Assert
        assertNotNull(response.getToken());
        assertEquals("user-1", response.getUserId());
    }

    @Test
    void testLogin_WrongPassword() {
        // Arrange
        org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder encoder = new org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder();
        String hashedPassword = encoder.encode("correct-password");

        User mockUser = new User();
        mockUser.setUsername("testuser");
        mockUser.setPassword(hashedPassword);
        mockUser.setStatus(User.Status.ACTIVE);

        when(userRepository.findByUsername("testuser")).thenReturn(Optional.of(mockUser));

        UserLoginRequest loginRequest = new UserLoginRequest();
        loginRequest.setUsername("testuser");
        loginRequest.setPassword("wrong-password");

        // Act & Assert
        assertThrows(IllegalArgumentException.class, () -> userService.login(loginRequest));
    }

    @Test
    void testUpdateUserWithPermissions() {
        // Arrange
        String userId = "user-1";
        User mockUser = new User();
        mockUser.setUserId(userId);
        mockUser.setUsername("Old Name");
        mockUser.setRole(User.Role.INSPECTOR); // Fix NPE
        mockUser.setStatus(User.Status.ACTIVE); // Fix NPE
        
        when(userRepository.findById(userId)).thenReturn(Optional.of(mockUser));
        when(projectRepository.findById("proj-1")).thenReturn(Optional.of(new Project("proj-1", "P1", "owner")));

        UpdateUserRequest request = new UpdateUserRequest();
        // request.setUsername("New Name"); // Username update is not supported in current DTO
        CreateUserRequest.ProjectPermissionDTO perm = new CreateUserRequest.ProjectPermissionDTO();
        perm.setProjectId("proj-1");
        perm.setPermission("READ_ONLY");
        request.setProjectPermissions(Collections.singletonList(perm));

        // Act
        userService.updateUser(userId, request);

        // Assert
        verify(userRepository, times(1)).save(any(User.class));
        verify(permissionRepository, times(1)).deleteByUserId(userId);
        verify(permissionRepository, times(1)).save(any(UserProjectPermission.class));
        // assertEquals("New Name", mockUser.getUsername()); // Removed assertion
    }
}

