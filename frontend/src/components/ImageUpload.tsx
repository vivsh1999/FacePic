import { useCallback, useState, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, CheckCircle, AlertCircle, Loader2, ImageIcon, User, Edit2, Check, Server, Eye } from 'lucide-react';
import { Link } from 'react-router-dom';
import { uploadAndProcess, getTaskStatus, updatePerson, type UploadWithFacesResponse, type DetectedFaceInfo, type UploadAndProcessResponse, type TaskStatusResponse } from '../services/api';

interface FileWithPreview extends File {
  preview?: string;
}

interface DetectionProgress {
  current: number;
  total: number;
  currentFile: string;
  facesFound: number;
}

export default function ImageUpload() {
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadWithFacesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);
  
  // State for uploaded images (before processing completes)
  const [uploadResult, setUploadResult] = useState<UploadAndProcessResponse | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const [processingComplete, setProcessingComplete] = useState(false);
  
  // State for face labeling
  const [faceLabels, setFaceLabels] = useState<Record<string, string>>({});
  const [editingFaceId, setEditingFaceId] = useState<string | null>(null);
  const [savingLabel, setSavingLabel] = useState<string | null>(null);
  
  // Poll for task status when processing in background
  useEffect(() => {
    if (!uploadResult?.task_id || processingComplete) return;
    
    const pollInterval = setInterval(async () => {
      try {
        const status = await getTaskStatus(uploadResult.task_id!);
        setTaskStatus(status);
        
        if (status.status === 'completed' || status.status === 'failed') {
          setProcessingComplete(true);
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error('Failed to get task status:', err);
      }
    }, 1000); // Poll every second
    
    return () => clearInterval(pollInterval);
  }, [uploadResult?.task_id, processingComplete]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const filesWithPreview = acceptedFiles.map((file) =>
      Object.assign(file, {
        preview: URL.createObjectURL(file),
      })
    );
    setFiles((prev) => [...prev, ...filesWithPreview]);
    setResult(null);
    setUploadResult(null);
    setTaskStatus(null);
    setProcessingComplete(false);
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
    
    abortRef.current = false;
    setError(null);
    setResult(null);
    setUploadResult(null);
    setTaskStatus(null);
    setProcessingComplete(false);

    try {
      // Fast upload with background processing
      setUploading(true);
      
      const response = await uploadAndProcess(files);
      setUploadResult(response);
      
      // Clear selected files (they're uploaded)
      files.forEach((file) => {
        if (file.preview) {
          URL.revokeObjectURL(file.preview);
        }
      });
      setFiles([]);
      setUploading(false);
      // Processing will continue in background, tracked via taskStatus
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = () => {
    abortRef.current = true;
  };

  const handleSaveLabel = async (face: DetectedFaceInfo) => {
    const newName = faceLabels[face.person_id];
    if (!newName?.trim()) return;
    
    setSavingLabel(face.person_id);
    try {
      await updatePerson(face.person_id, newName.trim());
      // Update the result to reflect the new name
      setResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          detected_faces: prev.detected_faces.map((f) =>
            f.person_id === face.person_id
              ? { ...f, person_name: newName.trim(), is_new_person: false }
              : f
          ),
        };
      });
      setEditingFaceId(null);
    } catch (err) {
      console.error('Failed to save label:', err);
    } finally {
      setSavingLabel(null);
    }
  };

  // Group detected faces by person
  const groupedFaces = result?.detected_faces.reduce((acc, face) => {
    if (!acc[face.person_id]) {
      acc[face.person_id] = {
        person_id: face.person_id,
        person_name: face.person_name,
        is_new_person: face.is_new_person,
        faces: [],
      };
    }
    acc[face.person_id].faces.push(face);
    return acc;
  }, {} as Record<string, { person_id: string; person_name: string | null; is_new_person: boolean; faces: DetectedFaceInfo[] }>);

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
            <p className="text-purple-600 text-sm mt-2 flex items-center justify-center gap-1">
              <Server className="h-4 w-4" />
              Fast &amp; accurate server-side detection (InsightFace)
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
            disabled={uploading || detecting || (detectionMode === 'client' && modelsLoading)}
            className="w-full py-3 px-4 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
          >
            {uploading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                {detectionMode === 'server' ? 'Uploading & detecting...' : 'Uploading...'}
              </>
            ) : detecting ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Detecting faces...
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

      {/* Face Detection Progress - only for client mode */}
      {detectionMode === 'client' && detecting && detectionProgress && (
        <div className="p-4 rounded-lg bg-purple-50 border border-purple-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Cpu className="h-5 w-5 text-purple-600" />
              <p className="font-medium text-purple-800">
                Detecting faces in your browser...
              </p>
            </div>
            <button
              onClick={handleCancel}
              className="text-sm text-purple-600 hover:text-purple-800"
            >
              Cancel
            </button>
          </div>
          
          {/* Progress bar */}
          <div className="mb-3">
            <div className="flex justify-between text-sm text-purple-700 mb-1">
              <span className="truncate max-w-[200px]">{detectionProgress.currentFile}</span>
              <span>{detectionProgress.current} / {detectionProgress.total}</span>
            </div>
            <div className="w-full bg-purple-200 rounded-full h-2.5">
              <div 
                className="bg-purple-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${(detectionProgress.current / detectionProgress.total) * 100}%` }}
              />
            </div>
          </div>
          
          {/* Stats */}
          <div className="flex gap-4 text-sm text-purple-700">
            <span className="flex items-center gap-1">
              <ImageIcon className="h-4 w-4" />
              {detectionProgress.current} scanned
            </span>
            <span>👤 {detectionProgress.facesFound} faces found</span>
          </div>
        </div>
      )}

      {/* Upload Result with Background Processing */}
      {uploadResult && (
        <div className="space-y-4">
          {/* Uploaded Images Summary */}
          <div className="p-4 rounded-lg bg-green-50 border border-green-200">
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium text-green-800">
                  {uploadResult.uploaded} {uploadResult.uploaded === 1 ? 'image' : 'images'} uploaded successfully!
                </p>
                {uploadResult.errors.length > 0 && (
                  <ul className="mt-2 text-sm text-amber-700 list-disc list-inside">
                    {uploadResult.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>

          {/* Processing Status */}
          {taskStatus && !processingComplete && (
            <div className="p-4 rounded-lg bg-purple-50 border border-purple-200">
              <div className="flex items-center gap-3 mb-3">
                <Loader2 className="h-5 w-5 text-purple-600 animate-spin" />
                <p className="font-medium text-purple-800">
                  Processing faces in background...
                </p>
              </div>
              <div className="w-full bg-purple-200 rounded-full h-2.5 mb-2">
                <div 
                  className="bg-purple-600 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${(taskStatus.progress / Math.max(taskStatus.total, 1)) * 100}%` }}
                />
              </div>
              <div className="flex gap-4 text-sm text-purple-700">
                <span>{taskStatus.progress} / {taskStatus.total} processed</span>
                <span>👤 {taskStatus.faces_detected} faces found</span>
              </div>
            </div>
          )}

          {/* Processing Complete */}
          {taskStatus && processingComplete && taskStatus.status === 'completed' && (
            <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-blue-800">Face detection complete!</p>
                  <div className="mt-2 text-sm text-blue-700 space-y-1">
                    <p>✓ {taskStatus.faces_detected} faces detected</p>
                    <p>✓ {taskStatus.persons_created} new people identified</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Processing Failed */}
          {taskStatus && processingComplete && taskStatus.status === 'failed' && (
            <div className="p-4 rounded-lg bg-red-50 border border-red-200">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-red-800">Face detection failed</p>
                  {taskStatus.errors.length > 0 && (
                    <ul className="mt-2 text-sm text-red-700 list-disc list-inside">
                      {taskStatus.errors.map((err: string, i: number) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Uploaded Images Grid */}
          {uploadResult.images.length > 0 && (
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-slate-900 flex items-center gap-2">
                  <ImageIcon className="h-5 w-5 text-slate-600" />
                  Uploaded Images ({uploadResult.images.length})
                </h3>
                <Link
                  to="/gallery"
                  className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
                >
                  <Eye className="h-4 w-4" />
                  View in Gallery
                </Link>
              </div>
              
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {uploadResult.images.map((image) => (
                  <Link
                    key={image.id}
                    to={`/gallery/${image.id}`}
                    className="relative group aspect-square rounded-lg overflow-hidden bg-slate-100"
                  >
                    {image.thumbnail_url ? (
                      <img
                        src={image.thumbnail_url}
                        alt={image.original_filename}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <ImageIcon className="h-8 w-8 text-slate-300" />
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                      <p className="text-white text-xs truncate">{image.original_filename}</p>
                    </div>
                    {/* Processing indicator */}
                    {!processingComplete && (
                      <div className="absolute top-1 right-1 px-1.5 py-0.5 bg-purple-600 rounded text-white text-xs flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" />
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Results - from client-side detection */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
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
                <div className="mt-2 text-sm text-green-700 space-y-1">
                  <p>✓ {result.faces_detected} faces detected</p>
                  <p>✓ {result.persons_created} new people identified</p>
                </div>
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

          {/* Detected Faces */}
          {groupedFaces && Object.keys(groupedFaces).length > 0 && (
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <h3 className="font-medium text-slate-900 mb-4 flex items-center gap-2">
                <User className="h-5 w-5 text-slate-600" />
                Detected Faces ({result.detected_faces.length})
              </h3>
              
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {Object.values(groupedFaces).map((group) => (
                  <div
                    key={group.person_id}
                    className={`relative rounded-lg border-2 p-2 ${
                      group.is_new_person
                        ? 'border-amber-300 bg-amber-50'
                        : 'border-slate-200 bg-slate-50'
                    }`}
                  >
                    {/* Face thumbnail */}
                    <div className="aspect-square rounded-md overflow-hidden bg-slate-200 mb-2">
                      {group.faces[0]?.thumbnail_url ? (
                        <img
                          src={group.faces[0].thumbnail_url}
                          alt="Face"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <User className="h-8 w-8 text-slate-400" />
                        </div>
                      )}
                    </div>

                    {/* Face count badge */}
                    {group.faces.length > 1 && (
                      <div className="absolute top-1 right-1 bg-primary-600 text-white text-xs px-1.5 py-0.5 rounded-full">
                        {group.faces.length}
                      </div>
                    )}

                    {/* Person name / label input */}
                    {group.is_new_person && editingFaceId !== group.person_id ? (
                      <button
                        onClick={() => {
                          setEditingFaceId(group.person_id);
                          setFaceLabels((prev) => ({ ...prev, [group.person_id]: '' }));
                        }}
                        className="w-full flex items-center justify-center gap-1 text-xs text-amber-700 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 rounded px-2 py-1.5 transition-colors"
                      >
                        <Edit2 className="h-3 w-3" />
                        Add name
                      </button>
                    ) : editingFaceId === group.person_id ? (
                      <div className="flex gap-1">
                        <input
                          type="text"
                          value={faceLabels[group.person_id] || ''}
                          onChange={(e) =>
                            setFaceLabels((prev) => ({
                              ...prev,
                              [group.person_id]: e.target.value,
                            }))
                          }
                          placeholder="Name"
                          className="flex-1 text-xs px-2 py-1 border border-slate-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleSaveLabel(group.faces[0]);
                            } else if (e.key === 'Escape') {
                              setEditingFaceId(null);
                            }
                          }}
                        />
                        <button
                          onClick={() => handleSaveLabel(group.faces[0])}
                          disabled={savingLabel === group.person_id || !faceLabels[group.person_id]?.trim()}
                          className="p-1 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                        >
                          {savingLabel === group.person_id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Check className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    ) : (
                      <p className="text-xs text-center text-slate-700 font-medium truncate">
                        {group.person_name}
                      </p>
                    )}

                    {/* New person indicator */}
                    {group.is_new_person && editingFaceId !== group.person_id && (
                      <p className="text-xs text-center text-amber-600 mt-1">New person</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
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
