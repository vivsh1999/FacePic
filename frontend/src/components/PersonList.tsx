import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, User, Edit2, Check, X, Image, RefreshCw, Users, Search } from 'lucide-react';
import { getPersons, updatePerson } from '../services/api';
import type { Person } from '../types';

const PERSONS_PER_PAGE = 24;

export default function PersonList() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [savingId, setSavingId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const fetchPersons = useCallback(async (skip: number, append = false, search?: string) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      
      const data = await getPersons(skip, PERSONS_PER_PAGE, undefined, search);
      
      if (append) {
        setPersons((prev) => [...prev, ...data]);
      } else {
        setPersons(data);
      }
      
      setHasMore(data.length === PERSONS_PER_PAGE);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load persons');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchPersons(0, false, searchQuery || undefined);
  }, [fetchPersons, searchQuery]);

  // Infinite scroll observer
  useEffect(() => {
    if (loading) return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore) {
          fetchPersons(persons.length, true, searchQuery || undefined);
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
  }, [loading, hasMore, loadingMore, persons.length, fetchPersons, searchQuery]);

  const startEditing = (person: Person) => {
    setEditingId(person.id);
    setEditName(person.name || '');
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditName('');
  };

  const saveName = async (personId: number) => {
    setSavingId(personId);
    try {
      const updated = await updatePerson(personId, editName);
      setPersons((prev) =>
        prev.map((p) => (p.id === personId ? { ...p, ...updated } : p))
      );
      setEditingId(null);
      setEditName('');
    } catch (err) {
      console.error('Update error:', err);
    } finally {
      setSavingId(null);
    }
  };

  const handleRefresh = () => {
    setPersons([]);
    setHasMore(true);
    fetchPersons(0, false, searchQuery || undefined);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-10 w-10 animate-spin text-primary-600 mb-4" />
        <p className="text-slate-500">Finding people in your photos...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <Users className="h-12 w-12 mx-auto text-slate-300 mb-4" />
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

  if (persons.length === 0 && !searchQuery) {
    return (
      <div className="text-center py-16">
        <User className="h-16 w-16 mx-auto text-slate-200 mb-4" />
        <h3 className="text-lg font-medium text-slate-700 mb-2">No people detected yet</h3>
        <p className="text-slate-500 mb-6">Upload photos with faces to see people here</p>
        <Link
          to="/upload"
          className="inline-block px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors shadow-sm hover:shadow-md"
        >
          Upload Photos
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with search and refresh */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <p className="text-sm text-slate-500">
          {persons.length} {persons.length === 1 ? 'person' : 'people'} detected
        </p>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-initial">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name..."
              className="w-full sm:w-64 pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={handleRefresh}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* No results for search */}
      {persons.length === 0 && searchQuery && (
        <div className="text-center py-12">
          <Search className="h-12 w-12 mx-auto text-slate-200 mb-4" />
          <p className="text-slate-500">No people found matching "{searchQuery}"</p>
        </div>
      )}

      {/* Person Grid */}
      {persons.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {persons.map((person) => (
            <div
              key={person.id}
              className="bg-white rounded-xl shadow-sm hover:shadow-lg transition-all duration-200 overflow-hidden hover:scale-[1.02]"
            >
              <Link to={`/people/${person.id}`}>
                <div className="aspect-square bg-slate-100 relative group">
                  {person.thumbnail_url ? (
                    <img
                      src={person.thumbnail_url}
                      alt={person.display_name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200">
                      <User className="h-16 w-16 text-slate-300" />
                    </div>
                  )}
                  {/* Photo count badge */}
                  <div className="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-full">
                    <Image className="h-3 w-3 text-white" />
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
                      className="flex-1 px-2 py-1 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveName(person.id);
                        if (e.key === 'Escape') cancelEditing();
                      }}
                    />
                    <button
                      onClick={() => saveName(person.id)}
                      disabled={savingId === person.id}
                      className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50"
                    >
                      {savingId === person.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                    </button>
                    <button
                      onClick={cancelEditing}
                      className="p-1.5 text-slate-400 hover:bg-slate-100 rounded transition-colors"
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
                      className="p-1.5 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                      title="Edit name"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
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
        {!hasMore && persons.length > PERSONS_PER_PAGE && (
          <p className="text-slate-400 text-sm">You've seen all people</p>
        )}
      </div>
    </div>
  );
}
