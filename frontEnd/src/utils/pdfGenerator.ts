import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { Task, TaskFile } from "./data";
import { filePreviewPath } from "./constans";
import { getUserId } from "./api";

// 创建HTML内容的辅助函数
const createHTMLContent = (task: Task): string => {
  // 计算总缺陷数
  const totalDefects = (task.TaskFiles || []).reduce((sum, file) => {
    if (file.VisionResult) {
      try {
        const visionData = JSON.parse(file.VisionResult);
        return (
          sum + (visionData.detection_count || visionData.totalDefects || 0)
        );
      } catch {
        return sum;
      }
    }
    return sum;
  }, 0);

  // 格式化日期
  const formatDate = (dateString: string): string => {
    if (!dateString) return "未知";
    try {
      return new Date(dateString).toLocaleString("zh-CN");
    } catch {
      return dateString;
    }
  };

  // 格式化状态
  const formatStatus = (status: string): string => {
    const statusMap: { [key: string]: string } = {
      completed: "已完成",
      failed: "失败",
      processing: "处理中",
      pending: "待处理",
      cancelled: "已取消",
    };
    return statusMap[status] || status;
  };

  // 处理Markdown内容
  const formatMarkdown = (markdown: string): string => {
    if (!markdown) return "";

    // 简单的Markdown转HTML处理
    return markdown
      .replace(/### (.*)/g, "<h3>$1</h3>")
      .replace(/## (.*)/g, "<h2>$1</h2>")
      .replace(/# (.*)/g, "<h1>$1</h1>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>")
      .replace(/^(.)/g, "<p>$1")
      .replace(/(.)$/g, "$1</p>");
  };

  // 格式化JSON
  const formatJSON = (jsonString: string): string => {
    try {
      const jsonObj = JSON.parse(jsonString);
      return JSON.stringify(jsonObj, null, 2);
    } catch {
      return jsonString;
    }
  };

  // 生成文件图片URL
  const getFileImageUrl = (file: TaskFile, projectId: string): string => {
    const baseUrl = window.location.origin;
    // return "https://so1.360tres.com/t01822d65d3533be80c.jpg";
    return `${baseUrl}${filePreviewPath}?FileId=${file.FileId}&ProjectId=${projectId}&UseId=${getUserId()}`;
  };

  // 构建HTML内容
  const html = `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>任务检测报告</title>
      <style>
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        
        body {
          font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
          line-height: 1.6;
          color: #333;
          background: white;
          padding: 40px;
          width: 800px;
        }
        
        .report-container {
          background: white;
          padding: 30px;
          border-radius: 8px;
        }
        
        .header {
          text-align: center;
          margin-bottom: 40px;
          border-bottom: 3px solid #1890ff;
          padding-bottom: 20px;
        }
        
        .header h1 {
          font-size: 28px;
          color: #1890ff;
          margin-bottom: 10px;
        }
        
        .section {
          margin-bottom: 30px;
          page-break-inside: avoid;
        }
        
        .section-title {
          font-size: 18px;
          font-weight: bold;
          color: #1890ff;
          margin-bottom: 15px;
          padding-bottom: 8px;
          border-bottom: 2px solid #f0f0f0;
        }
        
        .info-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 15px;
          margin-bottom: 20px;
        }
        
        .info-item {
          display: flex;
          margin-bottom: 8px;
        }
        
        .info-label {
          font-weight: bold;
          color: #666;
          min-width: 120px;
          flex-shrink: 0;
        }
        
        .info-value {
          color: #333;
          flex: 1;
          word-break: break-all;
        }
        
        .file-section {
          margin-top: 40px;
          padding-top: 30px;
          border-top: 2px solid #f0f0f0;
          page-break-before: always;
        }
        
        .file-header {
          background: #f8f9fa;
          padding: 15px;
          border-radius: 6px;
          margin-bottom: 20px;
        }
        
        .file-title {
          font-size: 16px;
          font-weight: bold;
          color: #1890ff;
          margin-bottom: 5px;
        }
        
        .content-block {
          background: #fafafa;
          padding: 15px;
          border-radius: 6px;
          margin-bottom: 15px;
          border-left: 4px solid #1890ff;
        }
        
        .content-title {
          font-weight: bold;
          color: #333;
          margin-bottom: 10px;
        }
        
        .markdown-content {
          line-height: 1.8;
        }
        
        .json-content {
          font-family: "Consolas", "Monaco", "Courier New", monospace;
          font-size: 12px;
          background: #f5f5f5;
          padding: 15px;
          border-radius: 4px;
          overflow-x: auto;
          white-space: pre-wrap;
          word-break: break-all;
        }
        
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 15px;
          margin-bottom: 20px;
        }
        
        .stat-item {
          background: #f8f9fa;
          padding: 15px;
          border-radius: 6px;
          text-align: center;
          border: 1px solid #e9ecef;
        }
        
        .stat-number {
          font-size: 24px;
          font-weight: bold;
          color: #1890ff;
          display: block;
        }
        
        .stat-label {
          font-size: 12px;
          color: #666;
          margin-top: 5px;
        }
        
        .file-image {
          max-width: 100%;
          height: auto;
          margin: 10px 0;
          border-radius: 4px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .image-container {
          text-align: center;
          margin: 20px 0;
        }
        
        .image-caption {
          font-size: 12px;
          color: #666;
          margin-top: 5px;
          font-style: italic;
        }
      </style>
    </head>
    <body>
      <div class="report-container">
        <!-- 报告头部 -->
        <div class="header">
          <h1>任务检测报告</h1>
          <p>生成时间：${new Date().toLocaleString("zh-CN")}</p>
        </div>
        
        <!-- 任务基本信息 -->
        <div class="section">
          <div class="section-title">任务基本信息</div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">任务ID：</span>
              <span class="info-value">${task.Id}</span>
            </div>
            <div class="info-item">
              <span class="info-label">任务名称：</span>
              <span class="info-value">${task.Name}</span>
            </div>
            <div class="info-item">
              <span class="info-label">项目ID：</span>
              <span class="info-value">${task.ProjectId}</span>
            </div>
            <div class="info-item">
              <span class="info-label">用户ID：</span>
              <span class="info-value">${task.UserId}</span>
            </div>
            <div class="info-item">
              <span class="info-label">算法类型：</span>
              <span class="info-value">${task.AlgorithmType}</span>
            </div>
            <div class="info-item">
              <span class="info-label">状态：</span>
              <span class="info-value">${formatStatus(task.Status)}</span>
            </div>
            <div class="info-item">
              <span class="info-label">进度：</span>
              <span class="info-value">${task.Progress}%</span>
            </div>
            <div class="info-item">
              <span class="info-label">描述：</span>
              <span class="info-value">${task.Description || "无描述"}</span>
            </div>
          </div>
        </div>
        
        <!-- 统计信息 -->
        <div class="section">
          <div class="section-title">处理统计</div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-number">${task.FileCount}</span>
              <span class="stat-label">总文件数</span>
            </div>
            <div class="stat-item">
              <span class="stat-number">${task.ProcessedFiles}</span>
              <span class="stat-label">已处理</span>
            </div>
            <div class="stat-item">
              <span class="stat-number">${task.SuccessFiles}</span>
              <span class="stat-label">成功</span>
            </div>
            <div class="stat-item">
              <span class="stat-number">${task.FailedFiles}</span>
              <span class="stat-label">失败</span>
            </div>
            <div class="stat-item">
              <span class="stat-number">${totalDefects}</span>
              <span class="stat-label">检测缺陷</span>
            </div>
          </div>
        </div>
        
        <!-- 时间信息 -->
        <div class="section">
          <div class="section-title">时间信息</div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">创建时间：</span>
              <span class="info-value">${formatDate(task.CreateTime)}</span>
            </div>
            <div class="info-item">
              <span class="info-label">更新时间：</span>
              <span class="info-value">${formatDate(task.UpdatedAt)}</span>
            </div>
            ${
              task.ProcessingStartTime
                ? `
            <div class="info-item">
              <span class="info-label">处理开始：</span>
              <span class="info-value">${formatDate(
                task.ProcessingStartTime
              )}</span>
            </div>
            `
                : ""
            }
            ${
              task.ProcessingEndTime
                ? `
            <div class="info-item">
              <span class="info-label">处理结束：</span>
              <span class="info-value">${formatDate(
                task.ProcessingEndTime
              )}</span>
            </div>
            `
                : ""
            }
          </div>
        </div>
        
        <!-- 文件详情 -->
        ${(task.TaskFiles || [])
          .map(
            (file, index) => `
          <div class="file-section">
            <div class="file-header">
              <div class="file-title">文件 ${index + 1}: ${file.FileName}</div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">文件ID：</span>
                  <span class="info-value">${file.FileId}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">状态：</span>
                  <span class="info-value">${formatStatus(file.Status)}</span>
                </div>
                ${
                  file.LogicalPath
                    ? `
                <div class="info-item">
                  <span class="info-label">路径：</span>
                  <span class="info-value">${file.LogicalPath}</span>
                </div>
                `
                    : ""
                }
                ${
                  file.ProcessingStartTime
                    ? `
                <div class="info-item">
                  <span class="info-label">处理开始：</span>
                  <span class="info-value">${formatDate(
                    file.ProcessingStartTime
                  )}</span>
                </div>
                `
                    : ""
                }
                ${
                  file.ProcessingEndTime
                    ? `
                <div class="info-item">
                  <span class="info-label">处理结束：</span>
                  <span class="info-value">${formatDate(
                    file.ProcessingEndTime
                  )}</span>
                </div>
                `
                    : ""
                }
                ${
                  file.ErrorMessage
                    ? `
                <div class="info-item">
                  <span class="info-label">错误信息：</span>
                  <span class="info-value">${file.ErrorMessage}</span>
                </div>
                `
                    : ""
                }
              </div>
            </div>
            
            <!-- 显示图片 -->
            ${
              file.LogicalPath
                ? `
            <div class="content-block">
              <div class="content-title">检测图片</div>
              <div class="image-container">
                <img src="${getFileImageUrl(file, task.ProjectId)}" alt="${
                    file.FileName
                  }" class="file-image" crossorigin="anonymous" />
                <div class="image-caption">${file.FileName}</div>
              </div>
            </div>
            `
                : ""
            }
            
            ${
              file.ManualResult || file.VisionResult
                ? `
            <div class="content-block">
              <div class="content-title">分析报告</div>
              <div class="markdown-content">
                ${formatMarkdown(file.ManualResult || file.VisionResult || "")}
              </div>
            </div>
            `
                : ""
            }
            
            ${
              file.VisionResult
                ? `
            <div class="content-block">
              <div class="content-title">视觉检测数据</div>
              <div class="json-content">${formatJSON(file.VisionResult)}</div>
            </div>
            `
                : ""
            }
          </div>
        `
          )
          .join("")}
      </div>
    </body>
    </html>
  `;

  return html;
};

// 简化的PDF生成器类 - 直接使用HTML转PDF
export class HTMLToPDFGenerator {
  public static async generateTaskPDF(task: Task): Promise<void> {
    try {
      // 创建HTML内容
      const htmlContent = createHTMLContent(task);

      // 创建iframe来隔离内容，避免影响主页面布局
      const iframe = document.createElement("iframe");
      iframe.style.position = "fixed";
      iframe.style.left = "-99999px";
      iframe.style.top = "-99999px";
      iframe.style.width = "800px";
      iframe.style.height = "600px";
      iframe.style.border = "none";
      iframe.style.visibility = "hidden";

      // 添加iframe到页面
      document.body.appendChild(iframe);

      // 写入HTML内容到iframe
      const iframeDoc =
        iframe.contentDocument || iframe.contentWindow?.document;
      if (!iframeDoc) {
        throw new Error("无法访问iframe文档");
      }

      iframeDoc.open();
      iframeDoc.write(htmlContent);
      iframeDoc.close();

      // 等待图片和内容加载完成
      await new Promise((resolve) => {
        const images = iframeDoc.querySelectorAll("img");
        let loadedImages = 0;
        const totalImages = images.length;

        if (totalImages === 0) {
          // 如果没有图片，等待500ms让其他内容渲染
          setTimeout(resolve, 500);
          return;
        }

        const checkAllLoaded = () => {
          loadedImages++;
          if (loadedImages >= totalImages) {
            // 所有图片加载完成后再等待200ms确保渲染完成
            setTimeout(resolve, 200);
          }
        };

        // 为每个图片添加加载事件监听
        images.forEach((img) => {
          if (img.complete) {
            checkAllLoaded();
          } else {
            img.onload = checkAllLoaded;
            img.onerror = checkAllLoaded; // 即使加载失败也继续
          }
        });

        // 设置超时，避免无限等待
        setTimeout(() => {
          resolve(undefined);
        }, 5000);
      });

      // 获取iframe的body元素
      const iframeBody = iframeDoc.body;
      if (!iframeBody) {
        throw new Error("iframe内容加载失败");
      }

      // 使用html2canvas转换整个内容（包括图片）
      const canvas = await html2canvas(iframeBody, {
        useCORS: true,
        allowTaint: true, // 允许跨域图片
        scale: 2,
        width: 800,
        backgroundColor: "#ffffff",
        logging: false,
        imageTimeout: 5000,
      });

      // 移除iframe
      document.body.removeChild(iframe);

      // 创建PDF - 简化版本，直接转换整个内容
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      // 计算图片尺寸，适应A4页面
      const margin = 10;
      const imgWidth = pageWidth - 2 * margin;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      // 如果内容高度超过一页，需要分页
      let currentY = 0;
      let pageNum = 0;

      while (currentY < imgHeight) {
        const remainingHeight = imgHeight - currentY;
        const pageContentHeight = Math.min(
          pageHeight - 2 * margin,
          remainingHeight
        );

        // 创建当前页的canvas
        const pageCanvas = document.createElement("canvas");
        const pageCtx = pageCanvas.getContext("2d");

        if (pageCtx) {
          const scale = canvas.width / imgWidth;
          const sourceY = currentY * scale;
          const sourceHeight = pageContentHeight * scale;

          pageCanvas.width = canvas.width;
          pageCanvas.height = sourceHeight;

          // 绘制当前页内容
          pageCtx.drawImage(
            canvas,
            0,
            sourceY,
            canvas.width,
            sourceHeight,
            0,
            0,
            canvas.width,
            sourceHeight
          );

          // 转换为数据URL
          const pageDataURL = pageCanvas.toDataURL("image/jpeg", 0.9);

          // 添加新页面
          if (pageNum > 0) {
            pdf.addPage();
          }

          // 添加图片到PDF
          pdf.addImage(
            pageDataURL,
            "JPEG",
            margin,
            margin,
            imgWidth,
            pageContentHeight
          );

          pageNum++;
        }

        currentY += pageContentHeight;
      }

      // 下载PDF
      const filename = `${task.Name}_检测报告_${
        new Date().toISOString().split("T")[0]
      }.pdf`;
      pdf.save(filename);
    } catch (error) {
      console.error("PDF生成失败:", error);
      throw error;
    }
  }
}

// 导出便捷函数
export const generateAndDownloadTaskPDF = async (task: Task): Promise<void> => {
  return HTMLToPDFGenerator.generateTaskPDF(task);
};
