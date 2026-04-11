'use client';

export const dynamic = 'force-dynamic';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

export default function AuthCallbackPage() {
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        const queryParams = searchParams;
        const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));

        const accessToken = queryParams.get('access_token') ?? hashParams.get('access_token');
        const errorParam = queryParams.get('error') ?? hashParams.get('error');
        const code = queryParams.get('code');
        const provider = queryParams.get('provider') ?? hashParams.get('provider');

        if (errorParam) {
          throw new Error(`OAuth error: ${errorParam}`);
        }

        if (accessToken) {
          const response = await fetch(`${apiUrl}/auth/me`, {
            headers: {
              Authorization: `Bearer ${accessToken}`
            }
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to fetch user profile');
          }

          const user = await response.json();
          localStorage.setItem('auth_token', accessToken);
          localStorage.setItem('auth_user', JSON.stringify(user));
          window.location.href = '/dashboard';
          return;
        }

        if (code && provider) {
          const response = await fetch(`${apiUrl}/auth/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, code })
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Authentication failed');
          }

          const data = await response.json();
          localStorage.setItem('auth_token', data.access_token);
          localStorage.setItem('auth_user', JSON.stringify(data.user));
          window.location.href = '/dashboard';
          return;
        }

        throw new Error('Authentication callback data is missing or invalid');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
        setLoading(false);
      }
    };

    handleCallback();
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-purple-900">
      <div className="text-center">
        {loading ? (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
            <p className="text-white text-lg">Authenticating...</p>
          </>
        ) : error ? (
          <>
            <div className="text-red-400 text-lg mb-4">❌ Authentication Failed</div>
            <p className="text-white mb-6">{error}</p>
            <a
              href="/login"
              className="bg-white text-blue-900 px-6 py-2 rounded-lg font-semibold hover:bg-gray-100"
            >
              Try Again
            </a>
          </>
        ) : null}
      </div>
    </div>
  );
}
