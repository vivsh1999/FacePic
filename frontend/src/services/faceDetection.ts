/**
 * Face detection service using face-api.js
 * Runs entirely in the browser using TensorFlow.js with WebGL acceleration
 */
import * as faceapi from 'face-api.js';

let modelsLoaded = false;
let loadingPromise: Promise<void> | null = null;

/**
 * Load face-api.js models
 */
export const loadModels = async (): Promise<void> => {
  if (modelsLoaded) return;
  
  // Prevent multiple simultaneous loads
  if (loadingPromise) {
    return loadingPromise;
  }
  
  loadingPromise = (async () => {
    const MODEL_URL = '/models';
    
    await Promise.all([
      faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    ]);
    
    modelsLoaded = true;
    console.log('Face detection models loaded');
  })();
  
  return loadingPromise;
};

/**
 * Check if models are loaded
 */
export const areModelsLoaded = (): boolean => modelsLoaded;

export interface DetectedFace {
  bbox: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  encoding: number[]; // 128-dimensional face descriptor
}

export interface FaceDetectionResult {
  faces: DetectedFace[];
  width: number;
  height: number;
}

/**
 * Detect faces in an image file
 */
export const detectFaces = async (file: File): Promise<FaceDetectionResult> => {
  // Ensure models are loaded
  await loadModels();
  
  // Create image element from file
  const img = await createImageFromFile(file);
  
  // Create a canvas with willReadFrequently for better performance
  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (ctx) {
    ctx.drawImage(img, 0, 0);
  }
  
  // Use canvas instead of img for detection (better performance with willReadFrequently)
  const inputElement = ctx ? canvas : img;
  
  // Detect faces with landmarks and descriptors
  const detections = await faceapi
    .detectAllFaces(inputElement, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5 }))
    .withFaceLandmarks()
    .withFaceDescriptors();
  
  // Clean up object URL
  URL.revokeObjectURL(img.src);
  
  const faces: DetectedFace[] = detections.map((detection) => {
    const box = detection.detection.box;
    return {
      bbox: {
        top: Math.round(box.top),
        right: Math.round(box.right),
        bottom: Math.round(box.bottom),
        left: Math.round(box.left),
      },
      encoding: Array.from(detection.descriptor), // Convert Float32Array to number[]
    };
  });
  
  return {
    faces,
    width: img.width,
    height: img.height,
  };
};

/**
 * Detect faces in multiple files
 */
export const detectFacesInFiles = async (
  files: File[],
  onProgress?: (current: number, total: number, filename: string) => void
): Promise<Map<File, FaceDetectionResult>> => {
  const results = new Map<File, FaceDetectionResult>();
  
  // Load models first
  await loadModels();
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (onProgress) {
      onProgress(i + 1, files.length, file.name);
    }
    
    try {
      const result = await detectFaces(file);
      results.set(file, result);
    } catch (error) {
      console.error(`Failed to detect faces in ${file.name}:`, error);
      // Store empty result on error
      results.set(file, { faces: [], width: 0, height: 0 });
    }
  }
  
  return results;
};

/**
 * Create an HTMLImageElement from a File
 */
const createImageFromFile = (file: File): Promise<HTMLImageElement> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
};

/**
 * Generate a face thumbnail as a base64 data URL
 */
export const generateFaceThumbnail = async (
  file: File,
  bbox: { top: number; right: number; bottom: number; left: number },
  size = 150
): Promise<string> => {
  const img = await createImageFromFile(file);
  
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Could not get canvas context');
  
  // Add padding around the face
  const padding = 0.3;
  const width = bbox.right - bbox.left;
  const height = bbox.bottom - bbox.top;
  const padX = width * padding;
  const padY = height * padding;
  
  const srcX = Math.max(0, bbox.left - padX);
  const srcY = Math.max(0, bbox.top - padY);
  const srcWidth = Math.min(img.width - srcX, width + 2 * padX);
  const srcHeight = Math.min(img.height - srcY, height + 2 * padY);
  
  canvas.width = size;
  canvas.height = size;
  
  ctx.drawImage(img, srcX, srcY, srcWidth, srcHeight, 0, 0, size, size);
  
  return canvas.toDataURL('image/jpeg', 0.9);
};
