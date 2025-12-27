import { useState, useEffect, useRef } from 'react';
import { Folder, File, ChevronRight, Home, RefreshCw, Search, SortAsc, SortDesc, Filter, Loader2 } from 'lucide-react';
import { listFiles, FileItem, getStats, ListFilesOptions } from '../services/api';
import type { Stats } from '../types';

export default function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sorting and filtering state
  const [sort, setSort] = useState<ListFilesOptions['sort']>('name');
  const [order, setOrder] = useState<ListFilesOptions['order']>('asc');
  const [filter, setFilter] = useState('');
  const [type, setType] = useState<ListFilesOptions['type']>('all');
  const prevPathRef = useRef(currentPath);
  const activePathRef = useRef(currentPath);

  useEffect(() => {
    activePathRef.current = currentPath;
  }, [currentPath]);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (prevPathRef.current !== currentPath) {
      setFiles([]);
      prevPathRef.current = currentPath;
    }
    loadFiles(currentPath);
  }, [currentPath, sort, order, filter, type]);

  const loadFiles = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFiles(path, { sort, order, filter, type });
      if (path === activePathRef.current) {
        setFiles(data);
      }
    } catch (err: any) {
      if (path !== activePathRef.current) return;
      
      if (err.response && err.response.status === 401) {
        // Ignore 401 for file listing on homepage, just don't show files
        setFiles([]);
      } else {
        setError('Failed to load files');
        console.error(err);
      }
    } finally {
      if (path === activePathRef.current) {
        setLoading(false);
      }
    }
  };

  const navigateTo = (path: string) => {
    setCurrentPath(path);
  };

  const breadcrumbs = currentPath.split('/').filter(Boolean);

  const formatSize = (bytes?: number) => {
    if (bytes === undefined) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  return (
    <div className="space-y-8">
      {/* Stats Section */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500 font-medium">Total Photos</p>
            <p className="text-2xl font-bold text-slate-900">{stats.total_images}</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500 font-medium">Faces Detected</p>
            <p className="text-2xl font-bold text-slate-900">{stats.total_faces}</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500 font-medium">People</p>
            <p className="text-2xl font-bold text-slate-900">{stats.total_persons}</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-sm text-slate-500 font-medium">Named</p>
            <p className="text-2xl font-bold text-slate-900">{stats.labeled_persons}</p>
          </div>
        </div>
      )}

      {/* File Browser Section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {/* Breadcrumbs */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
            <button 
              onClick={() => navigateTo('')}
              className="p-1 hover:bg-slate-200 rounded transition-colors"
            >
              <Home className="h-4 w-4" />
            </button>
            {breadcrumbs.length > 0 && <ChevronRight className="h-4 w-4 text-slate-400" />}
            {breadcrumbs.map((crumb, i) => (
              <div key={i} className="flex items-center gap-2">
                <button
                  onClick={() => navigateTo(breadcrumbs.slice(0, i + 1).join('/'))}
                  className="hover:text-primary-600 transition-colors"
                >
                  {crumb}
                </button>
                {i < breadcrumbs.length - 1 && (
                  <ChevronRight className="h-4 w-4 text-slate-400" />
                )}
              </div>
            ))}
          </div>
          <button 
            onClick={() => loadFiles(currentPath)}
            className="p-2 hover:bg-slate-200 rounded-lg transition-colors text-slate-500"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Toolbar */}
        <div className="p-4 border-b border-slate-100 flex flex-wrap items-center gap-4 bg-white">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter files..."
              className="w-full pl-9 pr-4 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* Type Filter */}
          <select
            value={type}
            onChange={(e) => setType(e.target.value as any)}
            className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="all">All Types</option>
            <option value="files">Files Only</option>
            <option value="folders">Folders Only</option>
          </select>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as any)}
              className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="name">Name</option>
              <option value="size">Size</option>
              <option value="date">Date</option>
            </select>
            <button
              onClick={() => setOrder(order === 'asc' ? 'desc' : 'asc')}
              className="p-1.5 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
              title={order === 'asc' ? 'Ascending' : 'Descending'}
            >
              {order === 'asc' ? <SortAsc className="h-4 w-4" /> : <SortDesc className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="divide-y divide-slate-100">
          {loading && files.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 opacity-20" />
              <p>Loading files...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center text-red-500">
              <p>{error}</p>
              <button 
                onClick={() => loadFiles(currentPath)}
                className="mt-4 text-sm font-medium text-primary-600 hover:underline"
              >
                Try again
              </button>
            </div>
          ) : files.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <Folder className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>This folder is empty</p>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50/50">
                  <th className="px-6 py-3">Name</th>
                  <th className="px-6 py-3">Size</th>
                  <th className="px-6 py-3">Modified</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {files.map((file) => (
                  <tr 
                    key={file.path}
                    className="hover:bg-slate-50 transition-colors cursor-pointer group"
                    onClick={() => file.is_directory && navigateTo(file.path)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        {file.is_directory ? (
                          <Folder className="h-5 w-5 text-blue-500 fill-blue-50" />
                        ) : (
                          <File className="h-5 w-5 text-slate-400" />
                        )}
                        <div className="flex flex-col">
                          <span className="text-sm font-medium text-slate-700 group-hover:text-primary-600">
                            {file.name}
                          </span>
                          {!file.is_directory && file.processed === false && (
                            <span className="flex items-center gap-1 text-xs text-amber-600 mt-0.5">
                              <Loader2 className="h-3 w-3 animate-spin" />
                              Processing...
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">
                      {file.is_directory ? '--' : formatSize(file.size)}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">
                      {file.modified_at ? new Date(file.modified_at * 1000).toLocaleDateString() : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
