import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Users, Trash2 } from 'lucide-react';
import { getImages, deleteImage } from '../services/api';
import type { Image } from '../types';

export default function Gallery() {
  const [images, setImages] = useState<Image[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchImages = async () => {
    try {
      setLoading(true);
      const data = await getImages(0, 100);
      setImages(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load images');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchImages();
  }, []);

  const handleDelete = async (imageId: number) => {
    if (!confirm('Are you sure you want to delete this image?')) return;

    try {
      await deleteImage(imageId);
      setImages((prev) => prev.filter((img) => img.id !== imageId));
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{error}</p>
        <button
          onClick={fetchImages}
          className="mt-4 text-primary-600 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500 mb-4">No images uploaded yet</p>
        <Link
          to="/upload"
          className="inline-block px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          Upload Images
        </Link>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {images.map((image) => (
        <div
          key={image.id}
          className="relative group aspect-square rounded-xl overflow-hidden bg-slate-100 shadow-sm hover:shadow-md transition-shadow"
        >
          <img
            src={image.thumbnail_url || image.image_url}
            alt={image.original_filename}
            className="w-full h-full object-cover"
            loading="lazy"
          />

          {/* Face count badge */}
          {image.face_count > 0 && (
            <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-1 bg-black/60 rounded-full">
              <Users className="h-3 w-3 text-white" />
              <span className="text-xs text-white font-medium">
                {image.face_count}
              </span>
            </div>
          )}

          {/* Processing status */}
          {image.processed === 0 && (
            <div className="absolute top-2 right-2 px-2 py-1 bg-amber-500 rounded-full">
              <span className="text-xs text-white font-medium">Processing</span>
            </div>
          )}

          {/* Hover overlay */}
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-end">
            <div className="w-full p-3 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-between">
              <p className="text-white text-sm truncate flex-1">
                {image.original_filename}
              </p>
              <button
                onClick={() => handleDelete(image.id)}
                className="p-1.5 bg-red-500 rounded-full hover:bg-red-600 text-white ml-2"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
