import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, User, Edit2, Check, X, Image, RefreshCw, Users, Search, Merge, ArrowRight } from 'lucide-react';
import { getPersons, updatePerson, mergePersons } from '../services/api';
import type { Person } from '../types';

const PERSONS_PER_PAGE = 24;

export default function PersonList() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  
  // Merge mode state
  const [mergeMode, setMergeMode] = useState(false);
  const [sourcePerson, setSourcePerson] = useState<Person | null>(null);
  const [targetPerson, setTargetPerson] = useState<Person | null>(null);
  const [merging, setMerging] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    setIsAdmin(localStorage.getItem('adminAuth') === 'true');
  }, []);

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

  const saveName = async (personId: string) => {
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

  // Merge mode handlers
  const enterMergeMode = () => {
    setMergeMode(true);
    setSourcePerson(null);
    setTargetPerson(null);
  };

  const exitMergeMode = () => {
    setMergeMode(false);
    setSourcePerson(null);
    setTargetPerson(null);
  };

  const handlePersonClickInMergeMode = (person: Person) => {
    if (!sourcePerson) {
      setSourcePerson(person);
    } else if (!targetPerson && person.id !== sourcePerson.id) {
      setTargetPerson(person);
    }
  };

  const handleMerge = async () => {
    if (!sourcePerson || !targetPerson) return;
    
    setMerging(true);
    try {
      await mergePersons(sourcePerson.id, targetPerson.id);
      // Remove source person from list and update target person
      setPersons((prev) => prev.filter((p) => p.id !== sourcePerson.id));
      // Refresh to get updated counts
      handleRefresh();
      exitMergeMode();
    } catch (err) {
      console.error('Merge error:', err);
      setError('Failed to merge persons');
    } finally {
      setMerging(false);
    }
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
      {/* Merge Mode Banner */}
      {mergeMode && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <Merge className="h-5 w-5 text-purple-600" />
              <div>
                <p className="font-medium text-purple-900">Merge Mode</p>
                <p className="text-sm text-purple-700">
                  {!sourcePerson
                    ? 'Select the first person (will be merged into the second)'
                    : !targetPerson
                    ? 'Now select the person to merge into'
                    : 'Ready to merge'}
                </p>
              </div>
            </div>
            
            {/* Selected persons preview */}
            {(sourcePerson || targetPerson) && (
              <div className="flex items-center gap-2">
                {sourcePerson && (
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-purple-200">
                    {sourcePerson.thumbnail_url ? (
                      <img src={sourcePerson.thumbnail_url} alt="" className="w-8 h-8 rounded-full object-cover" />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                        <User className="h-4 w-4 text-slate-400" />
                      </div>
                    )}
                    <span className="text-sm font-medium text-slate-700">{sourcePerson.display_name}</span>
                    <button
                      onClick={() => setSourcePerson(null)}
                      className="p-0.5 text-slate-400 hover:text-slate-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}
                
                {sourcePerson && targetPerson && (
                  <ArrowRight className="h-4 w-4 text-purple-400" />
                )}
                
                {targetPerson && (
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-purple-200">
                    {targetPerson.thumbnail_url ? (
                      <img src={targetPerson.thumbnail_url} alt="" className="w-8 h-8 rounded-full object-cover" />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                        <User className="h-4 w-4 text-slate-400" />
                      </div>
                    )}
                    <span className="text-sm font-medium text-slate-700">{targetPerson.display_name}</span>
                    <button
                      onClick={() => setTargetPerson(null)}
                      className="p-0.5 text-slate-400 hover:text-slate-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            )}
            
            <div className="flex items-center gap-2">
              {sourcePerson && targetPerson && (
                <button
                  onClick={handleMerge}
                  disabled={merging}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white font-medium rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                >
                  {merging ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Merging...
                    </>
                  ) : (
                    <>
                      <Merge className="h-4 w-4" />
                      Confirm Merge
                    </>
                  )}
                </button>
              )}
              <button
                onClick={exitMergeMode}
                className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      
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
              disabled={mergeMode}
            />
          </div>
          {!mergeMode && isAdmin && persons.length >= 2 && (
            <button
              onClick={enterMergeMode}
              className="p-2 text-slate-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
              title="Merge persons"
            >
              <Merge className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={handleRefresh}
            disabled={mergeMode}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
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
          {persons.map((person) => {
            const isSource = sourcePerson?.id === person.id;
            const isTarget = targetPerson?.id === person.id;
            const isSelected = isSource || isTarget;
            
            return (
              <div
                key={person.id}
                className={`bg-white rounded-xl shadow-sm hover:shadow-lg transition-all duration-200 overflow-hidden hover:scale-[1.02] ${
                  mergeMode ? 'cursor-pointer' : ''
                } ${isSelected ? 'ring-2 ring-purple-500 ring-offset-2' : ''}`}
                onClick={mergeMode ? () => handlePersonClickInMergeMode(person) : undefined}
              >
                {mergeMode ? (
                  // In merge mode, make the whole card clickable (no link)
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
                    {/* Selection indicator */}
                    {isSelected && (
                      <div className="absolute top-2 left-2 px-2 py-1 bg-purple-600 text-white text-xs font-medium rounded-full">
                        {isSource ? '1st' : '2nd'}
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
                ) : (
                  // Normal mode - link to person detail
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
                )}

                <div className="p-3">
                  {editingId === person.id && !mergeMode ? (
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
                      {!mergeMode && isAdmin && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            startEditing(person);
                          }}
                          className="p-1.5 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                          title="Edit name"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
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
