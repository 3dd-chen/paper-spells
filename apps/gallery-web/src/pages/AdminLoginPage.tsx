import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, setToken } from '../lib/adminApi';

export function AdminLoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const { token } = await login(username, password);
      setToken(token);
      navigate('/admin/rooms');
    } catch {
      setError('Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="paper-bg min-h-screen flex items-center justify-center p-6 text-ink">
      <div className="max-w-sm w-full sticker p-8 space-y-6">
        <div className="text-center">
          <h1 className="font-display text-3xl font-black text-ink">
            Admin <span className="italic text-cobalt">Panel</span>
          </h1>
          <p className="font-label text-xs text-inksoft mt-1.5 tracking-wide">Paper Spells Management</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            className="ps-field w-full px-4 py-3 text-sm"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="ps-field w-full px-4 py-3 text-sm"
            required
          />
          {error && <p className="font-label text-sm text-vermilion font-bold">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="ps-btn ps-btn-ink w-full py-3 px-6"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
