'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  BarChart3,
  TrendingUp,
  Calendar,
  Download,
  Trash2,
  Search,
  Filter,
  Eye,
  AlertCircle,
  Loader
} from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Task {
  id: string;
  keyword: string;
  location_name: string;
  search_volume?: number;
  traffic_opportunity?: number;
  verdict?: string;
  created_at: string;
  updated_at: string;
}

interface UserStats {
  total_analyses: number;
  average_traffic_opportunity: number;
  recent_tasks: Task[];
}

export default function ActivitiesPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading, token, user } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'opportunity'>('newest');

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, authLoading, router]);

  // Fetch user activities
  useEffect(() => {
    const fetchActivities = async () => {
      if (!isAuthenticated || !token) return;

      try {
        setLoading(true);
        
        // Fetch stats
        const statsResponse = await fetch(`${API_BASE}/stats`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!statsResponse.ok) throw new Error('Failed to fetch stats');
        const statsData = await statsResponse.json();
        setStats(statsData);

        // Fetch all tasks
        const tasksResponse = await fetch(`${API_BASE}/tasks?limit=100`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!tasksResponse.ok) throw new Error('Failed to fetch tasks');
        const tasksData = await tasksResponse.json();
        setTasks(tasksData.tasks);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load activities');
      } finally {
        setLoading(false);
      }
    };

    fetchActivities();
  }, [isAuthenticated, token]);

  // Handle search
  const handleSearch = async (keyword: string) => {
    setSearchTerm(keyword);
    
    if (!keyword.trim()) {
      // Reset to all tasks
      const tasksResponse = await fetch(`${API_BASE}/tasks?limit=100`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const tasksData = await tasksResponse.json();
      setTasks(tasksData.tasks);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/search?keyword=${encodeURIComponent(keyword)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setTasks(data.results);
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  // Sort tasks
  const sortedTasks = [...tasks].sort((a, b) => {
    switch (sortBy) {
      case 'oldest':
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case 'opportunity':
        return (b.traffic_opportunity || 0) - (a.traffic_opportunity || 0);
      case 'newest':
      default:
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
  });

  // Handle delete task
  const handleDeleteTask = async (taskId: string) => {
    if (!confirm('Are you sure you want to delete this task?')) return;

    try {
      const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) throw new Error('Failed to delete task');
      setTasks(tasks.filter(t => t.id !== taskId));
    } catch (err) {
      alert('Failed to delete task');
    }
  };

  // Handle download report
  const handleDownloadReport = async (taskId: string, format: 'csv' | 'pdf' = 'pdf') => {
    try {
      const response = await fetch(
        `${API_BASE}/tasks/${taskId}/download?format=${format}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Failed to download report');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis-${taskId}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert('Failed to download report');
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-900 to-purple-900 flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-12 h-12 animate-spin text-white mx-auto mb-4" />
          <p className="text-white text-lg">Loading your activities...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-black p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Activity History</h1>
              <p className="text-gray-300">View and manage your SEO analyses</p>
            </div>
            <Link
              href="/dashboard"
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition-all duration-200"
            >
              New Analysis
            </Link>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white/10 backdrop-blur-lg rounded-lg p-6 border border-white/20">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Total Analyses</p>
                    <p className="text-3xl font-bold text-white">{stats.total_analyses}</p>
                  </div>
                  <BarChart3 className="w-10 h-10 text-blue-400" />
                </div>
              </div>

              <div className="bg-white/10 backdrop-blur-lg rounded-lg p-6 border border-white/20">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Avg. Traffic Opportunity</p>
                    <p className="text-3xl font-bold text-white">
                      {(stats.average_traffic_opportunity || 0).toFixed(1)}%
                    </p>
                  </div>
                  <TrendingUp className="w-10 h-10 text-green-400" />
                </div>
              </div>

              <div className="bg-white/10 backdrop-blur-lg rounded-lg p-6 border border-white/20">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Recent Activity</p>
                    <p className="text-lg font-bold text-white">
                      {stats.recent_tasks.length > 0
                        ? new Date(stats.recent_tasks[0].created_at).toLocaleDateString()
                        : 'No data'}
                    </p>
                  </div>
                  <Calendar className="w-10 h-10 text-purple-400" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <p className="text-red-200">{error}</p>
          </div>
        )}

        {/* Search and Filter */}
        <div className="mb-6 bg-white/10 backdrop-blur-lg rounded-lg p-6 border border-white/20">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search by keyword..."
                value={searchTerm}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-400" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500"
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="opportunity">Highest Opportunity</option>
              </select>
            </div>
          </div>
        </div>

        {/* Tasks Table */}
        <div className="bg-white/10 backdrop-blur-lg rounded-lg border border-white/20 overflow-hidden">
          {sortedTasks.length === 0 ? (
            <div className="p-8 text-center">
              <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-300 text-lg">No analyses yet</p>
              <Link
                href="/dashboard"
                className="text-blue-400 hover:text-blue-300 mt-2 inline-block"
              >
                Create your first analysis →
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-white/5 border-b border-white/10">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-300">
                      Keyword
                    </th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-300">
                      Location
                    </th>
                    <th className="px-6 py-3 text-right text-sm font-semibold text-gray-300">
                      Search Volume
                    </th>
                    <th className="px-6 py-3 text-right text-sm font-semibold text-gray-300">
                      Opportunity
                    </th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-300">
                      Date
                    </th>
                    <th className="px-6 py-3 text-right text-sm font-semibold text-gray-300">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {sortedTasks.map((task) => (
                    <tr
                      key={task.id}
                      className="hover:bg-white/5 transition-colors duration-150"
                    >
                      <td className="px-6 py-4">
                        <div className="font-semibold text-white">{task.keyword}</div>
                        <div className="text-sm text-gray-400 mt-1">{task.verdict || 'N/A'}</div>
                      </td>
                      <td className="px-6 py-4 text-gray-300">{task.location_name}</td>
                      <td className="px-6 py-4 text-right text-white font-medium">
                        {task.search_volume?.toLocaleString() || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-500/20 text-green-300">
                          {(task.traffic_opportunity || 0).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-300 text-sm">
                        {new Date(task.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setSelectedTask(task)}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors duration-150"
                            title="View details"
                          >
                            <Eye className="w-4 h-4 text-blue-400" />
                          </button>
                          <button
                            onClick={() => handleDownloadReport(task.id, 'pdf')}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors duration-150"
                            title="Download PDF"
                          >
                            <Download className="w-4 h-4 text-green-400" />
                          </button>
                          <button
                            onClick={() => handleDeleteTask(task.id)}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors duration-150"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4 text-red-400" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Task Details Modal */}
        {selectedTask && (
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50"
            onClick={() => setSelectedTask(null)}
          >
            <div
              className="bg-gradient-to-br from-blue-900/80 to-purple-900/80 backdrop-blur-lg border border-white/20 rounded-lg p-6 max-w-2xl w-full"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-white">{selectedTask.keyword}</h2>
                <button
                  onClick={() => setSelectedTask(null)}
                  className="text-gray-400 hover:text-white"
                >
                  ✕
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <p className="text-gray-400 text-sm">Location</p>
                  <p className="text-white font-semibold">{selectedTask.location_name}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Search Volume</p>
                  <p className="text-white font-semibold">
                    {selectedTask.search_volume?.toLocaleString() || 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Traffic Opportunity</p>
                  <p className="text-green-400 font-semibold">
                    {(selectedTask.traffic_opportunity || 0).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Verdict</p>
                  <p className="text-white font-semibold">{selectedTask.verdict || 'N/A'}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-gray-400 text-sm">Created</p>
                  <p className="text-white font-semibold">
                    {new Date(selectedTask.created_at).toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => handleDownloadReport(selectedTask.id, 'pdf')}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg font-semibold transition-all duration-200"
                >
                  Download PDF Report
                </button>
                <button
                  onClick={() => handleDownloadReport(selectedTask.id, 'csv')}
                  className="flex-1 bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-lg font-semibold transition-all duration-200"
                >
                  Download CSV
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
