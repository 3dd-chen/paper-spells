import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getRooms, logout } from '../lib/adminApi';

export function AdminRoomsPage() {
  const [rooms, setRooms] = useState<{ room_id: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

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
    <div className="paper-bg min-h-screen p-6 text-ink">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="font-display text-4xl font-black text-ink">
            Rooms
          </h1>
          <button
            onClick={handleLogout}
            className="font-label text-sm text-inksoft hover:text-vermilion transition-colors underline decoration-2 underline-offset-4"
          >
            Sign out
          </button>
        </div>

        {loading ? (
          <p className="font-label text-inksoft text-center mt-16">Loading...</p>
        ) : rooms.length === 0 ? (
          <p className="font-label text-inksoft text-center mt-16">No rooms found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {rooms.map(room => (
              <button
                key={room.room_id}
                onClick={() => navigate(`/admin/rooms/${encodeURIComponent(room.room_id)}`)}
                className="sticker p-6 text-left hover:-translate-x-0.5 hover:-translate-y-0.5 transition-transform"
              >
                <p className="font-display font-black text-ink text-xl truncate">{room.room_id}</p>
                <p className="font-label text-sm text-inksoft mt-1">{room.count} artwork{room.count !== 1 ? 's' : ''}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
