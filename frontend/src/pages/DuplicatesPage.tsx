import { useState, useEffect } from 'react';
import { Loader2, Trash2, Copy, CheckCircle, AlertCircle, RefreshCw, Image } from 'lucide-react';
import { getDuplicates, deleteDuplicates, type DuplicatesResponse, type DuplicateGroup } from '../services/api';

function formatFileSize(bytes: number | null): string {
  if (!bytes) return 'Unknown size';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function DuplicatesPage() {
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [data, setData] = useState<DuplicatesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteResult, setDeleteResult] = useState<{ deleted: number; errors: string[] } | null>(null);

  const fetchDuplicates = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getDuplicates();
      setData(result);
      setSelectedIds(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load duplicates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDuplicates();
  }, []);

  const toggleSelection = (imageId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(imageId)) {
        next.delete(imageId);
      } else {
        next.add(imageId);
      }
      return next;
    });
  };

  const selectAllDuplicates = (group: DuplicateGroup) => {
    // Select all except the first (keep original)
    const duplicateIds = group.images.slice(1).map((img) => img.id);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      duplicateIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const selectAllDuplicatesInAllGroups = () => {
    if (!data) return;
    const allDuplicateIds = data.groups.flatMap((group) =>
      group.images.slice(1).map((img) => img.id)
    );
    setSelectedIds(new Set(allDuplicateIds));
  };

  const handleDelete = async () => {
    if (selectedIds.size === 0) return;

    setDeleting(true);
    setDeleteResult(null);
    try {
      const result = await deleteDuplicates(Array.from(selectedIds));
      setDeleteResult(result);
      // Refresh the list
      await fetchDuplicates();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-10 w-10 animate-spin text-primary-600 mb-4" />
        <p className="text-slate-500">Scanning for duplicate images...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <AlertCircle className="h-12 w-12 mx-auto text-red-400 mb-4" />
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={fetchDuplicates}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          <RefreshCw className="h-4 w-4" />
          Try again
        </button>
      </div>
    );
  }

  if (!data || data.total_groups === 0) {
    return (
      <div className="text-center py-16">
        <CheckCircle className="h-16 w-16 mx-auto text-green-400 mb-4" />
        <h3 className="text-lg font-medium text-slate-700 mb-2">No duplicates found!</h3>
        <p className="text-slate-500 mb-6">Your photo library is clean.</p>
        <button
          onClick={fetchDuplicates}
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
        >
          <RefreshCw className="h-4 w-4" />
          Scan again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Copy className="h-6 w-6 text-amber-500" />
            Duplicate Images
          </h1>
          <p className="text-slate-500 mt-1">
            Found {data.total_groups} {data.total_groups === 1 ? 'group' : 'groups'} with{' '}
            {data.total_duplicates} duplicate {data.total_duplicates === 1 ? 'image' : 'images'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={selectAllDuplicatesInAllGroups}
            className="px-3 py-2 text-sm bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
          >
            Select all duplicates
          </button>
          <button
            onClick={fetchDuplicates}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Delete Result */}
      {deleteResult && (
        <div
          className={`p-4 rounded-lg ${
            deleteResult.errors.length > 0 ? 'bg-amber-50 border border-amber-200' : 'bg-green-50 border border-green-200'
          }`}
        >
          <div className="flex items-start gap-3">
            {deleteResult.errors.length > 0 ? (
              <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
            ) : (
              <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
            )}
            <div>
              <p className={deleteResult.errors.length > 0 ? 'text-amber-800' : 'text-green-800'}>
                Successfully deleted {deleteResult.deleted} {deleteResult.deleted === 1 ? 'image' : 'images'}
              </p>
              {deleteResult.errors.length > 0 && (
                <ul className="mt-2 text-sm text-amber-700 list-disc list-inside">
                  {deleteResult.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Selection Bar */}
      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-10 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
          <p className="text-red-800 font-medium">
            {selectedIds.size} {selectedIds.size === 1 ? 'image' : 'images'} selected for deletion
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedIds(new Set())}
              className="px-3 py-1.5 text-slate-600 hover:bg-slate-100 rounded-lg text-sm"
            >
              Clear selection
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              {deleting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4" />
                  Delete Selected
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Duplicate Groups */}
      <div className="space-y-6">
        {data.groups.map((group) => (
          <div key={group.hash} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Image className="h-4 w-4 text-slate-400" />
                <span className="text-sm font-medium text-slate-700">
                  {group.images.length} identical images
                </span>
              </div>
              <button
                onClick={() => selectAllDuplicates(group)}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                Select duplicates
              </button>
            </div>

            <div className="p-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {group.images.map((image, index) => {
                const isSelected = selectedIds.has(image.id);
                const isOriginal = index === 0;

                return (
                  <div
                    key={image.id}
                    onClick={() => toggleSelection(image.id)}
                    className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                      isSelected
                        ? 'border-red-500 ring-2 ring-red-200'
                        : isOriginal
                        ? 'border-green-500'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {/* Original badge */}
                    {isOriginal && (
                      <div className="absolute top-2 left-2 px-2 py-0.5 bg-green-500 text-white text-xs font-medium rounded-full z-10">
                        Original
                      </div>
                    )}

                    {/* Selection checkbox */}
                    <div
                      className={`absolute top-2 right-2 w-5 h-5 rounded border-2 flex items-center justify-center z-10 ${
                        isSelected
                          ? 'bg-red-500 border-red-500'
                          : 'bg-white/80 border-slate-300'
                      }`}
                    >
                      {isSelected && (
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </div>

                    {/* Image */}
                    <div className="aspect-square bg-slate-100">
                      {image.thumbnail_url ? (
                        <img
                          src={image.thumbnail_url}
                          alt={image.original_filename}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Image className="h-8 w-8 text-slate-300" />
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="p-2 bg-white">
                      <p className="text-xs text-slate-900 truncate" title={image.original_filename}>
                        {image.original_filename}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatFileSize(image.file_size)} • {formatDate(image.uploaded_at)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
