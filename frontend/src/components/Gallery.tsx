import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Users, Trash2, RefreshCw, ImageOff, RotateCcw } from 'lucide-react';
import { getImages, deleteImage, reprocessImage, type UploadWithFacesRequest } from '../services/api';
import { detectFaces, loadModels, areModelsLoaded } from '../services/faceDetection';
import type { Image } from '../types';

const IMAGES_PER_PAGE = 20;

export default function Gallery() {
  const [images, setImages] = useState<Image[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const fetchImages = useCallback(async (skip: number, append = false) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      
      const data = await getImages(skip, IMAGES_PER_PAGE);
      
      if (append) {
        setImages((prev) => [...prev, ...data]);
      } else {
        setImages(data);
      }
      
      setHasMore(data.length === IMAGES_PER_PAGE);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load images');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchImages(0);
  }, [fetchImages]);

  // Infinite scroll observer
  useEffect(() => {
    if (loading) return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore) {
          fetchImages(images.length, true);
        }
      },
      { threshold: 0.1 }
    );

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [loading, hasMore, loadingMore, images.length, fetchImages]);

  const handleDelete = async (imageId: string) => {
    if (!confirm('Are you sure you want to delete this image?')) return;

    setDeletingId(imageId);
    try {
      await deleteImage(imageId);
      setImages((prev) => prev.filter((img) => img.id !== imageId));
    } catch (err) {
      console.error('Delete error:', err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleReprocess = async (image: Image) => {
    // Load models if not loaded
    if (!areModelsLoaded()) {
      try {
        await loadModels();
      } catch (err) {
        console.error('Failed to load face detection models:', err);
        return;
      }
    }

    setReprocessingId(image.id);
    try {
      // Fetch the image and run face detection
      const response = await fetch(image.image_url);
      const blob = await response.blob();
      const file = new File([blob], image.original_filename, { type: blob.type });
      
      const result = await detectFaces(file);
      
      const faceData: UploadWithFacesRequest = {
        faces: result.faces.map((f) => ({
          bbox: f.bbox,
          encoding: f.encoding,
        })),
        width: result.width,
        height: result.height,
      };
      
      const reprocessResult = await reprocessImage(image.id, faceData);
      
      // Update the image in the list with new face count
      if (reprocessResult.images.length > 0) {
        setImages((prev) =>
          prev.map((img) =>
            img.id === image.id
              ? { ...img, face_count: reprocessResult.faces_detected, processed: 1 }
              : img
          )
        );
      }
    } catch (err) {
      console.error('Reprocess error:', err);
    } finally {
      setReprocessingId(null);
    }
  };

  const handleRefresh = () => {
    setImages([]);
    setHasMore(true);
    fetchImages(0);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-10 w-10 animate-spin text-primary-600 mb-4" />
        <p className="text-slate-500">Loading your photos...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <ImageOff className="h-12 w-12 mx-auto text-slate-300 mb-4" />
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={handleRefresh}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Try again
        </button>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-16">
        <ImageOff className="h-16 w-16 mx-auto text-slate-200 mb-4" />
        <h3 className="text-lg font-medium text-slate-700 mb-2">No images yet</h3>
        <p className="text-slate-500 mb-6">Upload some photos to get started</p>
        <Link
          to="/upload"
          className="inline-block px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors shadow-sm hover:shadow-md"
        >
          Upload Images
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {images.length} {images.length === 1 ? 'photo' : 'photos'}
        </p>
        <button
          onClick={handleRefresh}
          className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Image Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {images.map((image) => (
          <div
            key={image.id}
            className="relative group aspect-square rounded-xl overflow-hidden bg-slate-100 shadow-sm hover:shadow-lg transition-all duration-200 hover:scale-[1.02]"
          >
            <img
              src={image.thumbnail_url || image.image_url}
              alt={image.original_filename}
              className="w-full h-full object-cover"
              loading="lazy"
            />

            {/* Face count badge */}
            {image.face_count > 0 && (
              <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-full">
                <Users className="h-3 w-3 text-white" />
                <span className="text-xs text-white font-medium">
                  {image.face_count}
                </span>
              </div>
            )}

            {/* Processing status */}
            {image.processed === 0 && (
              <div className="absolute top-2 right-2 px-2 py-1 bg-amber-500/90 backdrop-blur-sm rounded-full flex items-center gap-1">
                <Loader2 className="h-3 w-3 text-white animate-spin" />
                <span className="text-xs text-white font-medium">Processing</span>
              </div>
            )}

            {/* Reprocessing overlay */}
            {reprocessingId === image.id && (
              <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center">
                <Loader2 className="h-8 w-8 text-white animate-spin mb-2" />
                <span className="text-white text-sm">Detecting faces...</span>
              </div>
            )}

            {/* Hover overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end">
              <div className="w-full p-3 flex items-center justify-between">
                <p className="text-white text-sm truncate flex-1 font-medium">
                  {image.original_filename}
                </p>
                <div className="flex gap-1 ml-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleReprocess(image);
                    }}
                    disabled={reprocessingId === image.id}
                    className="p-2 bg-blue-500/90 backdrop-blur-sm rounded-full hover:bg-blue-600 text-white transition-colors disabled:opacity-50"
                    title="Reprocess faces"
                  >
                    {reprocessingId === image.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RotateCcw className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(image.id);
                    }}
                    disabled={deletingId === image.id}
                    className="p-2 bg-red-500/90 backdrop-blur-sm rounded-full hover:bg-red-600 text-white transition-colors disabled:opacity-50"
                    title="Delete image"
                  >
                    {deletingId === image.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Load more trigger / Loading indicator */}
      <div ref={loadMoreRef} className="py-8 flex justify-center">
        {loadingMore && (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Loading more...</span>
          </div>
        )}
        {!hasMore && images.length > IMAGES_PER_PAGE && (
          <p className="text-slate-400 text-sm">You've seen all photos</p>
        )}
      </div>
    </div>
  );
}
