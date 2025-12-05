import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, User, Edit2, Check, X, Images } from 'lucide-react';
import { getPersons, updatePerson } from '../services/api';
import type { Person } from '../types';

export default function PersonList() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');

  const fetchPersons = async () => {
    try {
      setLoading(true);
      const data = await getPersons(0, 100);
      setPersons(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load persons');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPersons();
  }, []);

  const startEditing = (person: Person) => {
    setEditingId(person.id);
    setEditName(person.name || '');
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditName('');
  };

  const saveName = async (personId: number) => {
    try {
      const updated = await updatePerson(personId, editName);
      setPersons((prev) =>
        prev.map((p) => (p.id === personId ? { ...p, ...updated } : p))
      );
      setEditingId(null);
      setEditName('');
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

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{error}</p>
        <button
          onClick={fetchPersons}
          className="mt-4 text-primary-600 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (persons.length === 0) {
    return (
      <div className="text-center py-12">
        <User className="h-12 w-12 mx-auto text-slate-300 mb-4" />
        <p className="text-slate-500 mb-4">No people detected yet</p>
        <Link
          to="/upload"
          className="inline-block px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          Upload Photos
        </Link>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {persons.map((person) => (
        <div
          key={person.id}
          className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow overflow-hidden"
        >
          <Link to={`/people/${person.id}`}>
            <div className="aspect-square bg-slate-100 relative">
              {person.thumbnail_url ? (
                <img
                  src={person.thumbnail_url}
                  alt={person.display_name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <User className="h-16 w-16 text-slate-300" />
                </div>
              )}
              {/* Photo count badge */}
              <div className="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 rounded-full">
                <Images className="h-3 w-3 text-white" />
                <span className="text-xs text-white font-medium">
                  {person.photo_count}
                </span>
              </div>
            </div>
          </Link>

          <div className="p-3">
            {editingId === person.id ? (
              <div className="flex items-center gap-1">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Enter name"
                  className="flex-1 px-2 py-1 text-sm border border-slate-300 rounded focus:outline-none focus:border-primary-500"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveName(person.id);
                    if (e.key === 'Escape') cancelEditing();
                  }}
                />
                <button
                  onClick={() => saveName(person.id)}
                  className="p-1 text-green-600 hover:bg-green-50 rounded"
                >
                  <Check className="h-4 w-4" />
                </button>
                <button
                  onClick={cancelEditing}
                  className="p-1 text-slate-400 hover:bg-slate-100 rounded"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <p
                  className={`text-sm font-medium truncate ${
                    person.name ? 'text-slate-900' : 'text-slate-400 italic'
                  }`}
                >
                  {person.display_name}
                </p>
                <button
                  onClick={() => startEditing(person)}
                  className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
