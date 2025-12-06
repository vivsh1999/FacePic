import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowLeft, Edit2, Check, X } from 'lucide-react';
import { getPersonPhotos, updatePerson } from '../services/api';
import type { PersonPhotosResponse } from '../types';

export default function PersonPhotos() {
  const { personId } = useParams<{ personId: string }>();
  const [data, setData] = useState<PersonPhotosResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');

  const fetchData = async () => {
    if (!personId) return;

    try {
      setLoading(true);
      const response = await getPersonPhotos(personId);
      setData(response);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [personId]);

  const startEditing = () => {
    setEditing(true);
    setEditName(data?.person.name || '');
  };

  const saveName = async () => {
    if (!personId || !data) return;

    try {
      const updated = await updatePerson(personId, editName);
      setData({
        ...data,
        person: { ...data.person, ...updated },
      });
      setEditing(false);
    } catch (err) {
      console.error('Update error:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{error || 'Person not found'}</p>
        <Link to="/people" className="mt-4 text-primary-600 hover:underline">
          Back to People
        </Link>
      </div>
    );
  }

  const { person, photos } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/people"
          className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-5 w-5 text-slate-600" />
        </Link>

        <div className="flex items-center gap-4 flex-1">
          {person.thumbnail_url && (
            <img
              src={person.thumbnail_url}
              alt={person.display_name}
              className="h-16 w-16 rounded-full object-cover border-2 border-white shadow-md"
            />
          )}

          <div className="flex-1">
            {editing ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Enter name"
                  className="px-3 py-1.5 text-lg font-semibold border border-slate-300 rounded-lg focus:outline-none focus:border-primary-500"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveName();
                    if (e.key === 'Escape') setEditing(false);
                  }}
                />
                <button
                  onClick={saveName}
                  className="p-2 text-green-600 hover:bg-green-50 rounded-lg"
                >
                  <Check className="h-5 w-5" />
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="p-2 text-slate-400 hover:bg-slate-100 rounded-lg"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1
                  className={`text-2xl font-bold ${
                    person.name ? 'text-slate-900' : 'text-slate-400 italic'
                  }`}
                >
                  {person.display_name}
                </h1>
                <button
                  onClick={startEditing}
                  className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
              </div>
            )}
            <p className="text-slate-500 text-sm">
              {person.photo_count} {person.photo_count === 1 ? 'photo' : 'photos'}
            </p>
          </div>
        </div>
      </div>

      {/* Photo Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {photos.map((photo) => (
          <div
            key={photo.id}
            className="relative aspect-square rounded-xl overflow-hidden bg-slate-100 shadow-sm hover:shadow-md transition-shadow"
          >
            <img
              src={photo.thumbnail_url || photo.image_url}
              alt={photo.original_filename}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        ))}
      </div>

      {photos.length === 0 && (
        <div className="text-center py-12">
          <p className="text-slate-500">No photos found for this person</p>
        </div>
      )}
    </div>
  );
}
