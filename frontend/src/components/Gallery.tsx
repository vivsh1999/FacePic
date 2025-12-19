import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Users, Trash2, RefreshCw, ImageOff, RotateCcw, Grid, List, Calendar, FileText, SortAsc, SortDesc } from 'lucide-react';
import { getImages, deleteImage } from '../services/api';
import type { Image } from '../types';

const IMAGES_PER_PAGE = 20;

type ViewMode = 'grid' | 'list';
type SortField = 'date' | 'name' | 'faces';
type SortOrder = 'asc' | 'desc';

export default function Gallery() {
  const [images, setImages] = useState<Image[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  
  // View and sort state
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

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

  const handleRefresh = () => {
    setImages([]);
    setHasMore(true);
    fetchImages(0);
  };

  // Sort images
  const sortedImages = useMemo(() => {
    const sorted = [...images].sort((a, b) => {
      let comparison = 0;
      
      switch (sortField) {
        case 'date':
          comparison = new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime();
          break;
        case 'name':
          comparison = a.original_filename.localeCompare(b.original_filename);
          break;
        case 'faces':
          comparison = a.face_count - b.face_count;
          break;
      }
      
      return sortOrder === 'asc' ? comparison : -comparison;
    });
    
    return sorted;
  }, [images, sortField, sortOrder]);

  const toggleSortOrder = () => {
    setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
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
      {/* Header with view/sort controls */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <p className="text-sm text-slate-500">
          {images.length} {images.length === 1 ? 'photo' : 'photos'}
        </p>
        
        <div className="flex items-center gap-2 flex-wrap">
          {/* Sort options */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => setSortField('date')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                sortField === 'date'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
              title="Sort by date"
            >
              <Calendar className="h-3 w-3" />
              Date
            </button>
            <button
              onClick={() => setSortField('name')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                sortField === 'name'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
              title="Sort by name"
            >
              <FileText className="h-3 w-3" />
              Name
            </button>
            <button
              onClick={() => setSortField('faces')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                sortField === 'faces'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
              title="Sort by face count"
            >
              <Users className="h-3 w-3" />
              Faces
            </button>
          </div>
          
          {/* Sort order */}
          <button
            onClick={toggleSortOrder}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
          >
            {sortOrder === 'asc' ? <SortAsc className="h-4 w-4" /> : <SortDesc className="h-4 w-4" />}
          </button>
          
          {/* View mode toggle */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
              title="Grid view"
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded transition-colors ${
                viewMode === 'list'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
              title="List view"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
          
          {/* Refresh */}
          <button
            onClick={handleRefresh}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Image Grid */}
      {viewMode === 'grid' && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {sortedImages.map((image) => (
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
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="space-y-2">
          {sortedImages.map((image) => (
            <div
              key={image.id}
              className="flex items-center gap-4 p-3 bg-white rounded-lg shadow-sm hover:shadow-md transition-all group"
            >
              {/* Thumbnail */}
              <div className="relative w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-slate-100">
                <img
                  src={image.thumbnail_url || image.image_url}
                  alt={image.original_filename}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                {reprocessingId === image.id && (
                  <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                    <Loader2 className="h-5 w-5 text-white animate-spin" />
                  </div>
                )}
              </div>
              
              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-900 truncate">{image.original_filename}</p>
                <div className="flex items-center gap-3 text-sm text-slate-500">
                  <span>{new Date(image.uploaded_at).toLocaleDateString()}</span>
                  {image.width && image.height && (
                    <span>{image.width} × {image.height}</span>
                  )}
                  {image.file_size && (
                    <span>{(image.file_size / 1024 / 1024).toFixed(1)} MB</span>
                  )}
                </div>
              </div>
              
              {/* Face count */}
              {image.face_count > 0 && (
                <div className="flex items-center gap-1 px-2 py-1 bg-slate-100 rounded-full">
                  <Users className="h-3 w-3 text-slate-500" />
                  <span className="text-xs font-medium text-slate-600">{image.face_count}</span>
                </div>
              )}
              
              {/* Processing status */}
              {image.processed === 0 && (
                <div className="flex items-center gap-1 px-2 py-1 bg-amber-100 rounded-full">
                  <Loader2 className="h-3 w-3 text-amber-600 animate-spin" />
                  <span className="text-xs font-medium text-amber-700">Processing</span>
                </div>
              )}
              
              {/* Actions */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleDelete(image.id)}
                  disabled={deletingId === image.id}
                  className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
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
          ))}
        </div>
      )}

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
