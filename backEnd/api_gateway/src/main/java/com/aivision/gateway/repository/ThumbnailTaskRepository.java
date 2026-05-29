package com.aivision.gateway.repository;

import com.aivision.gateway.model.ThumbnailTask;
import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ThumbnailTaskRepository extends JpaRepository<ThumbnailTask, String> {
    Optional<ThumbnailTask> findByFileId(String fileId);

    List<ThumbnailTask> findByFileIdIn(Collection<String> fileIds);

    List<ThumbnailTask> findByStatusInAndNextRunAtLessThanEqualOrderByCreatedAtAsc(
        Collection<ThumbnailTask.Status> statuses,
        LocalDateTime now,
        Pageable pageable);

    List<ThumbnailTask> findByStatusAndUpdatedAtLessThan(
        ThumbnailTask.Status status,
        LocalDateTime cutoff);
}
