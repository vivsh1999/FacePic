import React, { useState, useEffect } from 'react';
import { verifyAdmin, getStats } from '../services/api';
import { Stats } from '../types';
import DuplicatesPage from './DuplicatesPage';

const AdminPage: React.FC = () => {
  const [password, setPassword] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'duplicates'>('dashboard');

  useEffect(() => {
    const adminAuth = localStorage.getItem('adminAuth');
    if (adminAuth === 'true') {
      setIsLoggedIn(true);
      fetchStats();
    }
  }, []);

  const fetchStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (err: any) {
      console.error('Failed to fetch stats:', err);
      if (err.response && err.response.status === 401) {
        setIsLoggedIn(false);
        localStorage.removeItem('adminAuth');
        localStorage.removeItem('adminPassword');
      }
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await verifyAdmin(password);
      if (response.success) {
        setIsLoggedIn(true);
        localStorage.setItem('adminAuth', 'true');
        localStorage.setItem('adminPassword', password);
        fetchStats();
      } else {
        setError('Invalid password');
      }
    } catch (err) {
      setError('Failed to verify password');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    localStorage.removeItem('adminAuth');
    setPassword('');
  };

  if (!isLoggedIn) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6 text-center">Admin Login</h1>
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter admin password"
                required
              />
            </div>
            {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:bg-blue-300"
            >
              {loading ? 'Verifying...' : 'Login'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Admin Dashboard</h1>
        <button
          onClick={handleLogout}
          className="bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors"
        >
          Logout
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-8">
        <button
          className={`py-2 px-4 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'dashboard'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
          onClick={() => setActiveTab('dashboard')}
        >
          Dashboard
        </button>
        <button
          className={`py-2 px-4 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'duplicates'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
          onClick={() => setActiveTab('duplicates')}
        >
          Duplicates
        </button>
      </div>

      {activeTab === 'dashboard' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
              <h3 className="text-gray-500 text-sm font-medium uppercase tracking-wider">Total Images</h3>
              <p className="text-3xl font-bold mt-2">{stats?.total_images ?? '...'}</p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
              <h3 className="text-gray-500 text-sm font-medium uppercase tracking-wider">Total Faces</h3>
              <p className="text-3xl font-bold mt-2">{stats?.total_faces ?? '...'}</p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
              <h3 className="text-gray-500 text-sm font-medium uppercase tracking-wider">Total Persons</h3>
              <p className="text-3xl font-bold mt-2">{stats?.total_persons ?? '...'}</p>
            </div>
          </div>

          <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-100">
            <h2 className="text-xl font-semibold mb-4">System Information</h2>
            <div className="space-y-4">
              <div className="flex justify-between py-2 border-b border-gray-50">
                <span className="text-gray-600">Labeled Persons</span>
                <span className="font-medium">{stats?.labeled_persons ?? '...'}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-50">
                <span className="text-gray-600">Unlabeled Persons</span>
                <span className="font-medium">{stats?.unlabeled_persons ?? '...'}</span>
              </div>
            </div>
          </div>
          
          <div className="mt-8 p-6 bg-blue-50 rounded-lg border border-blue-100">
            <h2 className="text-lg font-semibold text-blue-800 mb-2">Admin Actions</h2>
            <p className="text-blue-600 mb-4">More administrative tools will be added here.</p>
            <div className="flex gap-4">
              <button 
                disabled
                className="bg-blue-600 text-white px-4 py-2 rounded opacity-50 cursor-not-allowed"
              >
                Re-index All Images
              </button>
              <button 
                disabled
                className="bg-red-600 text-white px-4 py-2 rounded opacity-50 cursor-not-allowed"
              >
                Clear Cache
              </button>
            </div>
          </div>
        </>
      )}

      {activeTab === 'duplicates' && (
        <DuplicatesPage />
      )}
    </div>
  );
};

export default AdminPage;
