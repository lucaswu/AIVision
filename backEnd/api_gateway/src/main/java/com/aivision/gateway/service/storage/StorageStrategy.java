package com.aivision.gateway.service.storage;

import java.io.InputStream;

public interface StorageStrategy {
    /**
     * 上传文件
     * @param inputStream 文件输入流
     * @param objectPath 存储路径（包含文件名）
     * @param contentType 文件类型
     * @param size 文件大小
     */
    void upload(InputStream inputStream, String objectPath, String contentType, long size);

    /**
     * 下载文件
     * @param objectPath 存储路径
     * @return 文件输入流
     */
    InputStream download(String objectPath);

    /**
     * 删除文件
     * @param objectPath 存储路径
     */
    void delete(String objectPath);

    /**
     * 检查文件是否存在
     * @param objectPath 存储路径
     * @return 是否存在
     */
    boolean exists(String objectPath);

    /**
     * 返回可被同一部署网络内其它服务读取的本地路径。
     * 只有共享本地卷存储支持；对象存储实现可返回 null。
     */
    default String resolveSharedPath(String objectPath) {
        return null;
    }
}
