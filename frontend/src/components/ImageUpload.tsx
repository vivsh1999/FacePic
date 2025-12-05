import { useCallback, useState, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, CheckCircle, AlertCircle, Loader2, ImageIcon } from 'lucide-react';
import { uploadImages, processImagesBackground, getTaskStatus } from '../services/api';
import type { UploadResponse, TaskStatusResponse } from '../types';

interface FileWithPreview extends File {
  preview?: string;
}

export default function ImageUpload() {
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const pollTaskStatus = async (taskId: string) => {
    try {
      const status = await getTaskStatus(taskId);
      setTaskStatus(status);
      
      if (status.status === 'completed' || status.status === 'failed') {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        setProcessing(false);
      }
    } catch (err) {
      console.error('Failed to get task status:', err);
    }
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const filesWithPreview = acceptedFiles.map((file) =>
      Object.assign(file, {
        preview: URL.createObjectURL(file),
      })
    );
    setFiles((prev) => [...prev, ...filesWithPreview]);
    setResult(null);
    setError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.bmp', '.webp'],
    },
    multiple: true,
  });

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const newFiles = [...prev];
      if (newFiles[index].preview) {
        URL.revokeObjectURL(newFiles[index].preview!);
      }
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setUploading(true);
    setError(null);
    setTaskStatus(null);

    try {
      const response = await uploadImages(files);
      setResult(response);

      // Clear uploaded files
      files.forEach((file) => {
        if (file.preview) {
          URL.revokeObjectURL(file.preview);
        }
      });
      setFiles([]);

      // Automatically process uploaded images in background
      if (response.uploaded > 0) {
        setProcessing(true);
        try {
          const bgResponse = await processImagesBackground(
            response.images.map((img) => img.id)
          );
          
          // Start polling for task status
          pollIntervalRef.current = window.setInterval(() => {
            pollTaskStatus(bgResponse.task_id);
          }, 1000);
          
          // Initial poll
          pollTaskStatus(bgResponse.task_id);
        } catch (err) {
          console.error('Processing error:', err);
          setProcessing(false);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-slate-300 hover:border-primary-400 hover:bg-slate-50'
        }`}
      >
        <input {...getInputProps()} />
        <Upload
          className={`h-12 w-12 mx-auto mb-4 ${
            isDragActive ? 'text-primary-500' : 'text-slate-400'
          }`}
        />
        {isDragActive ? (
          <p className="text-primary-600 font-medium">Drop the images here...</p>
        ) : (
          <div>
            <p className="text-slate-600 font-medium">
              Drag & drop images here, or click to select
            </p>
            <p className="text-slate-400 text-sm mt-1">
              Supports JPEG, PNG, GIF, BMP, WebP
            </p>
          </div>
        )}
      </div>

      {/* File Preview */}
      {files.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-slate-900">
              Selected Files ({files.length})
            </h3>
            <button
              onClick={() => {
                files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview));
                setFiles([]);
              }}
              className="text-sm text-slate-500 hover:text-slate-700"
            >
              Clear all
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="relative group aspect-square rounded-lg overflow-hidden bg-slate-100"
              >
                <img
                  src={file.preview}
                  alt={file.name}
                  className="w-full h-full object-cover"
                />
                <button
                  onClick={() => removeFile(index)}
                  className="absolute top-1 right-1 p-1 bg-black/50 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="h-4 w-4" />
                </button>
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                  <p className="text-white text-xs truncate">{file.name}</p>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleUpload}
            disabled={uploading || processing}
            className="w-full py-3 px-4 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
          >
            {uploading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-5 w-5" />
                Upload {files.length} {files.length === 1 ? 'image' : 'images'}
              </>
            )}
          </button>
        </div>
      )}

      {/* Processing Progress */}
      {processing && taskStatus && (
        <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
          <div className="flex items-center gap-3 mb-3">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <p className="font-medium text-blue-800">
              Processing images for face detection...
            </p>
          </div>
          
          {/* Progress bar */}
          <div className="mb-3">
            <div className="flex justify-between text-sm text-blue-700 mb-1">
              <span>Progress</span>
              <span>{taskStatus.progress} / {taskStatus.total}</span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2.5">
              <div 
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${(taskStatus.progress / taskStatus.total) * 100}%` }}
              />
            </div>
          </div>
          
          {/* Stats */}
          <div className="flex gap-4 text-sm text-blue-700">
            <span className="flex items-center gap-1">
              <ImageIcon className="h-4 w-4" />
              {taskStatus.processed} processed
            </span>
            <span>👤 {taskStatus.faces_detected} faces found</span>
          </div>
        </div>
      )}

      {/* Processing Complete */}
      {!processing && taskStatus?.status === 'completed' && (
        <div className="p-4 rounded-lg bg-green-50 border border-green-200">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-green-800">
                Processing complete!
              </p>
              <div className="mt-2 text-sm text-green-700 space-y-1">
                <p>✓ {taskStatus.processed} images processed</p>
                <p>✓ {taskStatus.faces_detected} faces detected</p>
                <p>✓ {taskStatus.persons_created} new people identified</p>
              </div>
              {taskStatus.errors.length > 0 && (
                <div className="mt-2 text-sm text-amber-700">
                  <p className="font-medium">Some errors occurred:</p>
                  <ul className="list-disc list-inside">
                    {taskStatus.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !processing && !taskStatus && (
        <div
          className={`p-4 rounded-lg ${
            result.failed > 0 ? 'bg-amber-50' : 'bg-green-50'
          }`}
        >
          <div className="flex items-start gap-3">
            {result.failed > 0 ? (
              <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
            ) : (
              <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
            )}
            <div>
              <p
                className={`font-medium ${
                  result.failed > 0 ? 'text-amber-800' : 'text-green-800'
                }`}
              >
                {result.uploaded} {result.uploaded === 1 ? 'image' : 'images'}{' '}
                uploaded successfully
                {result.failed > 0 && `, ${result.failed} failed`}
              </p>
              {result.errors.length > 0 && (
                <ul className="mt-2 text-sm text-amber-700 list-disc list-inside">
                  {result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="font-medium text-red-800">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
