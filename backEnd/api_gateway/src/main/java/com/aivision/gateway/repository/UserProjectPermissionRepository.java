package com.aivision.gateway.repository;

import com.aivision.gateway.model.UserProjectPermission;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface UserProjectPermissionRepository extends JpaRepository<UserProjectPermission, String> {
    List<UserProjectPermission> findByUserId(String userId);
    List<UserProjectPermission> findByProjectId(String projectId);
    Optional<UserProjectPermission> findByUserIdAndProjectId(String userId, String projectId);
    void deleteByUserId(String userId);
}


