import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Upload, Image, Users, Camera, ArrowRight } from 'lucide-react';
import { getStats } from '../services/api';
import type { Stats } from '../types';

export default function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(console.error);
  }, []);

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center py-12">
        <div className="flex justify-center mb-6">
          <div className="p-4 bg-primary-100 rounded-2xl">
            <Camera className="h-16 w-16 text-primary-600" />
          </div>
        </div>
        <h1 className="text-4xl font-bold text-slate-900 mb-4">
          Welcome to ImageTag
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl mx-auto mb-8">
          Upload your photos, let AI detect faces, and organize your memories by
          the people in them — just like Google Photos.
        </p>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-6 py-3 bg-primary-600 text-white font-medium rounded-xl hover:bg-primary-700 transition-colors"
        >
          <Upload className="h-5 w-5" />
          Upload Photos
          <ArrowRight className="h-5 w-5" />
        </Link>
      </div>

      {/* Stats Section */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-xl">
                <Image className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">
                  {stats.total_images}
                </p>
                <p className="text-slate-500">Photos</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 rounded-xl">
                <Users className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">
                  {stats.total_persons}
                </p>
                <p className="text-slate-500">People Detected</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-100 rounded-xl">
                <Users className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">
                  {stats.labeled_persons}
                </p>
                <p className="text-slate-500">People Named</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Features Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-8">
        <div className="text-center p-6">
          <div className="inline-flex p-3 bg-slate-100 rounded-xl mb-4">
            <Upload className="h-8 w-8 text-slate-600" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-2">
            Bulk Upload
          </h3>
          <p className="text-slate-500">
            Upload multiple photos at once with drag & drop support
          </p>
        </div>

        <div className="text-center p-6">
          <div className="inline-flex p-3 bg-slate-100 rounded-xl mb-4">
            <Users className="h-8 w-8 text-slate-600" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-2">
            Face Detection
          </h3>
          <p className="text-slate-500">
            AI automatically detects and groups faces in your photos
          </p>
        </div>

        <div className="text-center p-6">
          <div className="inline-flex p-3 bg-slate-100 rounded-xl mb-4">
            <Camera className="h-8 w-8 text-slate-600" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-2">
            Browse by Person
          </h3>
          <p className="text-slate-500">
            Name people and view all their photos in one place
          </p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap justify-center gap-4 pt-8">
        <Link
          to="/gallery"
          className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-700"
        >
          <Image className="h-4 w-4" />
          View Gallery
        </Link>
        <Link
          to="/people"
          className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-700"
        >
          <Users className="h-4 w-4" />
          View People
        </Link>
      </div>
    </div>
  );
}
