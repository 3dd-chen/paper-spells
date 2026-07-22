import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, setToken } from '../lib/adminApi';

export function AdminLoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const stars = useMemo(() => {
    return Array.from({ length: 20 }).map((_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      size: Math.random() * 2.5 + 1,
      duration: `${Math.random() * 4 + 2}s`,
      delay: `${Math.random() * 5}s`,
    }));
  }, []);

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
    <div className="cosmic-bg min-h-screen flex items-center justify-center p-6 text-white relative overflow-hidden">
      {/* Background Twinkling Stars */}
      {stars.map((star) => (
        <div
          key={star.id}
          className="star-twinkle absolute rounded-full bg-white pointer-events-none"
          style={{
            left: star.left,
            top: star.top,
            width: star.size,
            height: star.size,
            '--twinkle-duration': star.duration,
            animationDelay: star.delay,
            boxShadow: star.size > 2 ? '0 0 6px rgba(255, 255, 255, 0.8)' : 'none',
          } as React.CSSProperties}
        />
      ))}
      <div className="max-w-sm w-full cosmic-card p-8 space-y-6 relative">
        <div className="text-center">
          <h1 className="starwars-text text-[1.8rem] leading-[1.0] font-black tracking-wider">
            Admin Panel
          </h1>
          <p className="font-label text-xs text-white/60 mt-2.5 tracking-wide">Paper Spells Management</p>
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
            className="ps-btn ps-btn-ink w-full py-3 px-6 text-white"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
