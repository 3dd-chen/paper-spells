import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { getRooms, logout } from '../lib/adminApi';

export function AdminRoomsPage() {
  const [rooms, setRooms] = useState<{ room_id: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const stars = useMemo(() => {
    return Array.from({ length: 30 }).map((_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      size: Math.random() * 3 + 1,
      duration: `${Math.random() * 4 + 2}s`,
      delay: `${Math.random() * 5}s`,
    }));
  }, []);

  useEffect(() => {
    getRooms()
      .then(setRooms)
      .catch(() => navigate('/admin/login'))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLogout = async () => {
    await logout();
    navigate('/admin/login');
  };

  return (
    <div className="cosmic-bg min-h-screen p-6 text-white relative overflow-hidden">
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
      <div className="max-w-3xl mx-auto relative z-10">
        <div className="flex justify-between items-center mb-8">
          <h1 className="starwars-text text-[2.2rem] leading-[1.0] font-black tracking-wider">
            Rooms
          </h1>
          <button
            onClick={handleLogout}
            className="font-label text-sm text-white/60 hover:text-vermilion transition-colors underline decoration-2 underline-offset-4"
          >
            Sign out
          </button>
        </div>

        {loading ? (
          <p className="font-label text-white/60 text-center mt-16">Loading...</p>
        ) : rooms.length === 0 ? (
          <p className="font-label text-white/60 text-center mt-16">No rooms found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {rooms.map(room => (
              <button
                key={room.room_id}
                onClick={() => navigate(`/admin/rooms/${encodeURIComponent(room.room_id)}`)}
                className="cosmic-card p-6 text-left hover:-translate-x-0.5 hover:-translate-y-0.5 transition-transform"
              >
                <p className="font-display font-black text-white text-xl truncate">{room.room_id}</p>
                <p className="font-label text-sm text-white/60 mt-1">{room.count} artwork{room.count !== 1 ? 's' : ''}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
