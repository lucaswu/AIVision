import { decode as decodePng } from "fast-png";
import * as dicomParser from "dicom-parser";
import * as UTIF from "utif";

export interface ImageStats {
  mean: number;
  std: number;
  min: number;
  max: number;
}

export interface WindowLevelValue {
  ww: number;
  wl: number;
}

export interface DecodedGrayscaleImage {
  width: number;
  height: number;
  rawData: Float32Array;
  stats: ImageStats;
  bitDepth: number;
  format: "browser" | "png" | "tiff" | "dicom";
  isHighBit: boolean;
  suggestedInitialWindow: WindowLevelValue;
}

interface DecodeCacheEntry extends DecodedGrayscaleImage {}

const decodedImageCache = new Map<string, DecodeCacheEntry>();
const pendingDecodeCache = new Map<string, Promise<DecodeCacheEntry>>();
const MAX_CACHE_SIZE = 20;

const DICOM_EXTENSIONS = new Set(["dcm", "dicom", "dic", "diconde"]);
const TIFF_EXTENSIONS = new Set(["tif", "tiff"]);

function getCacheKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}-${file.type}`;
}

export function getFileExtension(fileName?: string): string {
  if (!fileName) return "";
  const ext = fileName.split(".").pop();
  return ext ? ext.toLowerCase() : "";
}

export function isHighBitPreviewCandidate(fileName?: string): boolean {
  const ext = getFileExtension(fileName);
  return ext === "png" || TIFF_EXTENSIONS.has(ext) || DICOM_EXTENSIONS.has(ext);
}

function setDecodedCache(key: string, entry: DecodeCacheEntry) {
  if (decodedImageCache.size >= MAX_CACHE_SIZE) {
    const oldestKey = decodedImageCache.keys().next().value;
    if (oldestKey) decodedImageCache.delete(oldestKey);
  }
  decodedImageCache.set(key, entry);
}

export function getDecodedImageFromCache(file: File): DecodeCacheEntry | undefined {
  const key = getCacheKey(file);
  const cached = decodedImageCache.get(key);
  if (!cached) return undefined;

  decodedImageCache.delete(key);
  decodedImageCache.set(key, cached);
  return cached;
}

export async function preprocessToGrayCache(file: File): Promise<void> {
  const key = getCacheKey(file);
  if (decodedImageCache.has(key)) return;
  if (pendingDecodeCache.has(key)) {
    await pendingDecodeCache.get(key);
    return;
  }

  const pending = decodeImageFile(file)
    .then((entry) => {
      setDecodedCache(key, entry);
      return entry;
    })
    .finally(() => {
      pendingDecodeCache.delete(key);
    });

  pendingDecodeCache.set(key, pending);
  await pending;
}

export async function decodeImageFile(file: File): Promise<DecodeCacheEntry> {
  const ext = getFileExtension(file.name);

  if (DICOM_EXTENSIONS.has(ext) || file.type === "application/dicom") {
    return decodeDicomFile(file);
  }
  if (TIFF_EXTENSIONS.has(ext) || file.type === "image/tiff") {
    return decodeTiffFile(file);
  }
  if (ext === "png" || file.type === "image/png") {
    return decodePngFile(file);
  }
  return decodeBrowserImage(file);
}

export function calculateStatsFromRawData(
  data: ArrayLike<number>,
  x: number = 0,
  y: number = 0,
  w: number = -1,
  h: number = -1,
  imgWidth: number = 0,
  step: number = 1
): ImageStats | null {
  if (!imgWidth || data.length === 0) return null;

  const width = w === -1 ? imgWidth : w;
  const height = h === -1 ? Math.floor(data.length / imgWidth) : h;

  let count = 0;
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let mean = 0;
  let m2 = 0;

  for (let row = y; row < y + height; row += step) {
    for (let col = x; col < x + width; col += step) {
      const index = row * imgWidth + col;
      if (index < 0 || index >= data.length) continue;

      const value = data[index];
      count += 1;
      const delta = value - mean;
      mean += delta / count;
      const delta2 = value - mean;
      m2 += delta * delta2;

      if (value < min) min = value;
      if (value > max) max = value;
    }
  }

  if (count === 0) return null;

  return {
    mean,
    std: Math.sqrt(m2 / count),
    min,
    max,
  };
}

export function getAutoWindowFromStats(stats: ImageStats): WindowLevelValue {
  const ww = Math.max(1, Math.min(4 * stats.std, stats.max - stats.min));
  return {
    ww,
    wl: stats.mean,
  };
}

export function getFullRangeWindowFromStats(stats: ImageStats): WindowLevelValue {
  return {
    ww: Math.max(1, stats.max - stats.min),
    wl: (stats.max + stats.min) / 2,
  };
}

export function getEditorInitialWindow(entry: DecodedGrayscaleImage): WindowLevelValue {
  if (entry.isHighBit || entry.format === "dicom") {
    return getAutoWindowFromStats(entry.stats);
  }
  return {
    ww: 255,
    wl: 128,
  };
}

export function getPreviewInitialWindow(entry: DecodedGrayscaleImage): WindowLevelValue {
  if (entry.isHighBit || entry.format === "dicom") {
    return getAutoWindowFromStats(entry.stats);
  }
  return getFullRangeWindowFromStats(entry.stats);
}

export function applyWindowLevelToRawData(
  data: ArrayLike<number>,
  ww: number,
  wl: number
): Uint8Array {
  const safeWW = Math.max(1, ww);
  const windowMin = wl - safeWW / 2;
  const windowMax = wl + safeWW / 2;
  const result = new Uint8Array(data.length);

  for (let i = 0; i < data.length; i += 1) {
    const value = data[i];
    if (value <= windowMin) {
      result[i] = 0;
    } else if (value >= windowMax) {
      result[i] = 255;
    } else {
      result[i] = Math.round(((value - windowMin) / safeWW) * 255);
    }
  }

  return result;
}

export function renderDisplayDataToCanvas(
  canvas: HTMLCanvasElement,
  displayData: Uint8Array,
  width: number,
  height: number
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = width;
  canvas.height = height;

  const imageData = new ImageData(width, height);
  const rgba = imageData.data;

  for (let i = 0; i < displayData.length; i += 1) {
    const value = displayData[i];
    const offset = i * 4;
    rgba[offset] = value;
    rgba[offset + 1] = value;
    rgba[offset + 2] = value;
    rgba[offset + 3] = 255;
  }

  ctx.putImageData(imageData, 0, 0);
}

function makeDecodedEntry(
  rawData: Float32Array,
  width: number,
  height: number,
  bitDepth: number,
  format: DecodeCacheEntry["format"]
): DecodeCacheEntry {
  const stats = calculateStatsFromRawData(rawData, 0, 0, -1, -1, width, 2);
  if (!stats) {
    throw new Error("无法计算图像统计信息");
  }

  return {
    rawData,
    width,
    height,
    bitDepth,
    format,
    isHighBit: bitDepth > 8,
    stats,
    suggestedInitialWindow:
      bitDepth > 8 || format === "dicom"
        ? getAutoWindowFromStats(stats)
        : { ww: 255, wl: 128 },
  };
}

async function decodeBrowserImage(file: File): Promise<DecodeCacheEntry> {
  const url = URL.createObjectURL(file);
  const img = new Image();

  try {
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = reject;
      img.src = url;
    });

    const width = img.naturalWidth;
    const height = img.naturalHeight;
    const tempCanvas = document.createElement("canvas");
    tempCanvas.width = width;
    tempCanvas.height = height;
    const tempCtx = tempCanvas.getContext("2d", { willReadFrequently: true });
    if (!tempCtx) {
      throw new Error("无法创建临时画布");
    }

    tempCtx.drawImage(img, 0, 0);
    const { data } = tempCtx.getImageData(0, 0, width, height);
    const gray = new Float32Array(width * height);

    for (let i = 0; i < gray.length; i += 1) {
      const offset = i * 4;
      gray[i] =
        0.299 * data[offset] +
        0.587 * data[offset + 1] +
        0.114 * data[offset + 2];
    }

    return makeDecodedEntry(gray, width, height, 8, "browser");
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function decodePngFile(file: File): Promise<DecodeCacheEntry> {
  const buffer = await file.arrayBuffer();
  const decoded = decodePng(new Uint8Array(buffer));
  const { width, height, depth, channels, data } = decoded;
  const maxSourceValue = depth < 8 ? (1 << depth) - 1 : depth === 16 ? 65535 : 255;
  const scale = depth < 8 ? 255 / maxSourceValue : 1;
  const gray = new Float32Array(width * height);

  for (let i = 0; i < width * height; i += 1) {
    const offset = i * channels;
    if (channels === 1 || channels === 2) {
      gray[i] = Number(data[offset]) * scale;
    } else {
      const r = Number(data[offset]) * scale;
      const g = Number(data[offset + 1]) * scale;
      const b = Number(data[offset + 2]) * scale;
      gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
    }
  }

  return makeDecodedEntry(gray, width, height, depth < 8 ? 8 : depth, "png");
}

async function decodeTiffFile(file: File): Promise<DecodeCacheEntry> {
  const buffer = await file.arrayBuffer();
  const ifds = UTIF.decode(buffer);
  const imageIfd = ifds.find((ifd: any) => ifd?.t256 && ifd?.t257) ?? ifds[0];
  if (!imageIfd) {
    throw new Error("TIFF 中未找到可解码图像");
  }

  UTIF.decodeImage(buffer, imageIfd, ifds);

  const width = imageIfd.width;
  const height = imageIfd.height;
  const bitsPerSample = Math.min(32, imageIfd["t258"]?.[0] ?? 8);
  const sampleFormat = imageIfd["t339"]?.[0] ?? 1;
  const photometric = imageIfd["t262"]?.[0] ?? 2;
  const samplesPerPixel = imageIfd["t277"]?.[0] ?? imageIfd["t258"]?.length ?? 1;

  if (
    (photometric === 0 || photometric === 1) &&
    (bitsPerSample === 8 || bitsPerSample === 16) &&
    samplesPerPixel === 1
  ) {
    const gray = new Float32Array(width * height);
    const rawBytes = imageIfd.data as Uint8Array;

    if (bitsPerSample === 8) {
      for (let i = 0; i < gray.length; i += 1) {
        const value = rawBytes[i];
        gray[i] = photometric === 0 ? 255 - value : value;
      }
    } else {
      const view = new DataView(rawBytes.buffer, rawBytes.byteOffset, rawBytes.byteLength);
      for (let i = 0; i < gray.length; i += 1) {
        const value =
          sampleFormat === 2
            ? view.getInt16(i * 2, true)
            : view.getUint16(i * 2, true);
        gray[i] = photometric === 0 ? 65535 - value : value;
      }
    }

    return makeDecodedEntry(gray, width, height, bitsPerSample, "tiff");
  }

  const rgba = UTIF.toRGBA8(imageIfd) as Uint8Array;
  const gray = new Float32Array(width * height);
  for (let i = 0; i < gray.length; i += 1) {
    const offset = i * 4;
    gray[i] =
      0.299 * rgba[offset] +
      0.587 * rgba[offset + 1] +
      0.114 * rgba[offset + 2];
  }

  return makeDecodedEntry(gray, width, height, 8, "tiff");
}

async function decodeDicomFile(file: File): Promise<DecodeCacheEntry> {
  const buffer = await file.arrayBuffer();
  const byteArray = new Uint8Array(buffer);
  const dataSet = dicomParser.parseDicom(byteArray);

  const width = dataSet.uint16("x00280011");
  const height = dataSet.uint16("x00280010");
  const bitsAllocated = dataSet.uint16("x00280100") ?? 8;
  const bitsStored = dataSet.uint16("x00280101") ?? bitsAllocated;
  const pixelRepresentation = dataSet.uint16("x00280103") ?? 0;
  const samplesPerPixel = dataSet.uint16("x00280002") ?? 1;
  const planarConfiguration = dataSet.uint16("x00280006") ?? 0;
  const transferSyntaxUid = dataSet.string("x00020010") ?? "1.2.840.10008.1.2";
  const slope = dataSet.floatString("x00281053") ?? 1;
  const intercept = dataSet.floatString("x00281052") ?? 0;
  const pixelDataElement = dataSet.elements.x7fe00010;

  if (!width || !height || !pixelDataElement) {
    throw new Error("DICOM 缺少像素数据或尺寸信息");
  }
  if (pixelDataElement.encapsulatedPixelData) {
    throw new Error("暂不支持压缩 DICOM");
  }
  if (bitsAllocated !== 8 && bitsAllocated !== 16) {
    throw new Error(`暂不支持 ${bitsAllocated} 位 DICOM`);
  }

  const pixelCount = width * height;
  const gray = new Float32Array(pixelCount);
  const parser =
    transferSyntaxUid === "1.2.840.10008.1.2.2"
      ? dicomParser.bigEndianByteArrayParser
      : dicomParser.littleEndianByteArrayParser;

  if (samplesPerPixel === 1) {
    const bytesPerSample = bitsAllocated / 8;
    for (let i = 0; i < pixelCount; i += 1) {
      const offset = pixelDataElement.dataOffset + i * bytesPerSample;
      let sample =
        bitsAllocated === 16
          ? pixelRepresentation === 1
            ? parser.readInt16(byteArray, offset)
            : parser.readUint16(byteArray, offset)
          : byteArray[offset];
      sample = normalizeStoredDicomSample(sample, bitsStored, pixelRepresentation);
      gray[i] = sample * slope + intercept;
    }
  } else if (samplesPerPixel === 3 && bitsAllocated === 8) {
    for (let i = 0; i < pixelCount; i += 1) {
      let r: number;
      let g: number;
      let b: number;

      if (planarConfiguration === 1) {
        r = byteArray[pixelDataElement.dataOffset + i];
        g = byteArray[pixelDataElement.dataOffset + pixelCount + i];
        b = byteArray[pixelDataElement.dataOffset + pixelCount * 2 + i];
      } else {
        const offset = pixelDataElement.dataOffset + i * 3;
        r = byteArray[offset];
        g = byteArray[offset + 1];
        b = byteArray[offset + 2];
      }

      gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
    }
  } else {
    throw new Error("暂不支持该 DICOM 像素格式");
  }

  return makeDecodedEntry(gray, width, height, bitsStored, "dicom");
}

function normalizeStoredDicomSample(
  sample: number,
  bitsStored: number,
  pixelRepresentation: number
): number {
  if (bitsStored >= 16) {
    return sample;
  }

  const mask = (1 << bitsStored) - 1;
  let value = sample & mask;
  if (pixelRepresentation === 1) {
    const signBit = 1 << (bitsStored - 1);
    if (value & signBit) {
      value -= 1 << bitsStored;
    }
  }
  return value;
}
