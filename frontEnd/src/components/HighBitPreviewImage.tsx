import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  applyWindowLevelToRawData,
  getDecodedImageFromCache,
  getFileExtension,
  getPreviewInitialWindow,
  isHighBitPreviewCandidate,
  preprocessToGrayCache,
  renderDisplayDataToCanvas,
  type DecodedGrayscaleImage,
} from "@/utils/highBitImage";

interface HighBitPreviewImageProps {
  src: string;
  fileName?: string;
  alt?: string;
  style?: React.CSSProperties;
  className?: string;
}

const placeholderStyle: React.CSSProperties = {
  background: "#f5f5f5",
  color: "#999",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 12,
};

const HighBitPreviewImage: React.FC<HighBitPreviewImageProps> = ({
  src,
  fileName,
  alt = "preview",
  style,
  className,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const extension = useMemo(() => getFileExtension(fileName), [fileName]);
  const nativeFallbackAllowed = extension === "png";
  const [decoded, setDecoded] = useState<DecodedGrayscaleImage | null>(null);
  const [renderMode, setRenderMode] = useState<"native" | "canvas">(
    isHighBitPreviewCandidate(fileName) ? "canvas" : "native"
  );
  const [loading, setLoading] = useState<boolean>(isHighBitPreviewCandidate(fileName));
  const [error, setError] = useState<string | null>(null);

  const shouldProbe = useMemo(() => isHighBitPreviewCandidate(fileName), [fileName]);

  useEffect(() => {
    if (!shouldProbe) {
      setDecoded(null);
      setRenderMode("native");
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setDecoded(null);

    const loadImage = async () => {
      try {
        const response = await fetch(src);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const blob = await response.blob();
        const resolvedName = fileName || `preview.${getFileExtension(fileName) || "img"}`;
        const file = new File([blob], resolvedName, {
          type: blob.type || "application/octet-stream",
        });

        await preprocessToGrayCache(file);
        if (cancelled) return;

        const cached = getDecodedImageFromCache(file);
        if (!cached) {
          throw new Error("解码缓存未命中");
        }

        const useCanvas =
          cached.format === "tiff" ||
          cached.format === "dicom" ||
          cached.isHighBit;

        setDecoded(cached);
        setRenderMode(useCanvas ? "canvas" : "native");
        setLoading(false);
      } catch (loadError) {
        if (cancelled) return;
        console.error("预览图加载失败:", loadError);
        setRenderMode(nativeFallbackAllowed ? "native" : "canvas");
        setLoading(false);
        setError(loadError instanceof Error ? loadError.message : "预览失败");
      }
    };

    loadImage();
    return () => {
      cancelled = true;
    };
  }, [fileName, nativeFallbackAllowed, shouldProbe, src]);

  useEffect(() => {
    if (renderMode !== "canvas" || !decoded || !canvasRef.current) return;

    const initialWindow = getPreviewInitialWindow(decoded);
    const displayData = applyWindowLevelToRawData(
      decoded.rawData,
      initialWindow.ww,
      initialWindow.wl
    );
    renderDisplayDataToCanvas(
      canvasRef.current,
      displayData,
      decoded.width,
      decoded.height
    );
  }, [decoded, renderMode]);

  if (loading) {
    return (
      <div className={className} style={{ ...placeholderStyle, ...style }}>
        图像加载中...
      </div>
    );
  }

  if (renderMode === "canvas" && decoded) {
    return (
      <canvas
        ref={canvasRef}
        className={className}
        width={decoded.width}
        height={decoded.height}
        style={style}
      />
    );
  }

  if (error && (!nativeFallbackAllowed || renderMode === "canvas")) {
    return (
      <div className={className} style={{ ...placeholderStyle, ...style }}>
        {error}
      </div>
    );
  }

  return <img src={src} alt={alt} className={className} style={style} />;
};

export default HighBitPreviewImage;
