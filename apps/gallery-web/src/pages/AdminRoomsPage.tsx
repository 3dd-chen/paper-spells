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
    <div className="min-h-screen bg-gradient-to-b from-rose-50 to-pink-100 p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-500 to-violet-500">
            Rooms
          </h1>
          <button
            onClick={handleLogout}
            className="text-sm text-slate-500 hover:text-pink-500 transition-colors"
          >
            Sign out
          </button>
        </div>

        {loading ? (
          <p className="text-slate-400 text-center mt-16">Loading...</p>
        ) : rooms.length === 0 ? (
          <p className="text-slate-400 text-center mt-16">No rooms found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {rooms.map(room => (
              <button
                key={room.room_id}
                onClick={() => navigate(`/admin/rooms/${encodeURIComponent(room.room_id)}`)}
                className="bg-white/80 backdrop-blur-xl rounded-2xl border border-white/50 p-6 text-left shadow hover:shadow-pink-200 hover:border-pink-200 transition-all"
              >
                <p className="font-bold text-slate-700 text-lg truncate">{room.room_id}</p>
                <p className="text-sm text-slate-400 mt-1">{room.count} artwork{room.count !== 1 ? 's' : ''}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
