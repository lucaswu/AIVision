package com.aivision.gateway.repository;

import com.aivision.gateway.model.Directory;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface DirectoryRepository extends JpaRepository<Directory, String> {

    /**
     * 根据目录ID、项目ID查找目录
     */
    Optional<Directory> findByDirIdAndProjectIdAndStatus(String dirId, String projectId, Directory.Status status);

    /**
     * 根据项目ID、父目录ID和目录名称查找目录（用于检查重名）
     */
    Optional<Directory> findByProjectIdAndParentIdAndDirNameAndStatus(String projectId, String parentId, String dirName, Directory.Status status);

    /**
     * 根据父目录ID查找所有子目录（不限用户）
     */
    List<Directory> findByParentIdAndStatus(String parentId, Directory.Status status);

    /**
     * 根据父目录ID查找所有子目录（不限用户）
     */
    List<Directory> findByParentIdAndStatusOrderByDirNameAsc(String parentId, Directory.Status status);

    /**
     * 根据父目录ID和项目ID查找所有子目录（不限用户）
     */
    List<Directory> findByProjectIdAndParentIdAndStatus(String projectId, String parentId, Directory.Status status);

    /**
     * 根据路径前缀查找活跃目录（用于重命名后同步子目录路径）
     */
    List<Directory> findByProjectIdAndStatusAndDirPathStartingWith(String projectId, Directory.Status status, String dirPathPrefix);

    /**
     * 根据项目ID、用户ID和父目录ID查找目录
     */
    List<Directory> findByProjectIdAndUserIdAndParentIdAndStatus(String projectId, String userId, String parentId, Directory.Status status);

    /**
     * 根据项目ID、用户ID、父目录ID和目录名称查找目录（用于检查重名）
     */
    Optional<Directory> findByProjectIdAndUserIdAndParentIdAndDirNameAndStatus(String projectId, String userId, String parentId, String dirName, Directory.Status status);

    /**
     * 根据目录ID、项目ID和用户ID查找目录
     */
    Optional<Directory> findByDirIdAndProjectIdAndUserIdAndStatus(String dirId, String projectId, String userId, Directory.Status status);

    /**
     * 根据父目录ID和用户ID查找所有子目录
     */
    List<Directory> findByParentIdAndUserIdAndStatusOrderByDirNameAsc(String parentId, String userId, Directory.Status status);

    /**
     * 根据项目ID和用户ID查找根目录（没有父目录的目录）
     */
    List<Directory> findByProjectIdAndUserIdAndParentIdIsNullAndStatusOrderByDirNameAsc(String projectId, String userId, Directory.Status status);

    /**
     * 检查目录层级深度
     */
    @Query("SELECT d.dirLevel FROM Directory d WHERE d.dirId = :dirId AND d.status = :status")
    Optional<Integer> findDirLevelByDirIdAndStatus(@Param("dirId") String dirId, @Param("status") Directory.Status status);

    /**
     * 根据项目ID查找所有目录（用于构建文件树）
     */
    List<Directory> findByProjectIdAndStatusOrderByDirLevelAscSortOrderAscDirNameAsc(String projectId, Directory.Status status);

    /**
     * 根据项目ID删除所有目录
     */
    void deleteByProjectId(String projectId);
}
