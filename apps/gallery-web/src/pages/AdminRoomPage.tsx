import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getRoomArtworks, hideArtwork, unhideArtwork, deleteArtwork, type AdminArtwork } from '../lib/adminApi';
import { resolveVideoUrl } from '../lib/videoUrl';

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-700',
  generating: 'bg-yellow-100 text-yellow-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-slate-100 text-slate-500',
};

const STATUS_ICONS: Record<string, string> = {
  generating: '⏳',
  failed: '❌',
  pending: '🕐',
};

export function AdminRoomPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const [artworks, setArtworks] = useState<AdminArtwork[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => {
    if (!roomId) return;
    getRoomArtworks(roomId)
      .then(setArtworks)
      .catch(() => navigate('/admin/login'))
      .finally(() => setLoading(false));
  }, [roomId, navigate]);

  const handleToggleHide = async (artwork: AdminArtwork) => {
    setPendingId(artwork.id);
    try {
      if (artwork.hidden) {
        await unhideArtwork(artwork.id);
      } else {
        await hideArtwork(artwork.id);
      }
      setArtworks(prev =>
        prev.map(a => a.id === artwork.id ? { ...a, hidden: artwork.hidden ? 0 : 1 } : a)
      );
    } finally {
      setPendingId(null);
    }
  };

  const handleDelete = async (artwork: AdminArtwork) => {
    if (!confirm(`Delete this artwork? This cannot be undone.`)) return;
    setPendingId(artwork.id);
    try {
      await deleteArtwork(artwork.id);
      setArtworks(prev => prev.filter(a => a.id !== artwork.id));
    } catch {
      alert('Failed to delete artwork.');
    } finally {
      setPendingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-rose-50 to-pink-100 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate('/admin/rooms')}
            className="text-sm text-slate-400 hover:text-pink-500 transition-colors"
          >
            ← Rooms
          </button>
          <h1 className="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-500 to-violet-500">
            {roomId}
          </h1>
          <span className="ml-auto text-sm text-slate-400">{artworks.length} items</span>
        </div>

        {loading ? (
          <p className="text-slate-400 text-center mt-16">Loading...</p>
        ) : artworks.length === 0 ? (
          <p className="text-slate-400 text-center mt-16">No artworks in this room.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {artworks.map(artwork => {
              const videoSrc = artwork.video_url ? resolveVideoUrl(artwork.video_url) : null;
              const imgSrc = artwork.image_path ? resolveVideoUrl(artwork.image_path) : null;

              return (
                <div
                  key={artwork.id}
                  className={`bg-white/80 backdrop-blur-xl rounded-2xl border overflow-hidden shadow transition-all ${artwork.hidden ? 'opacity-50 border-slate-200' : 'border-white/50'}`}
                >
                  {/* Media Preview */}
                  <div className="aspect-video bg-slate-100 relative overflow-hidden flex items-center justify-center">
                    {videoSrc ? (
                      <video
                        src={videoSrc}
                        className="w-full h-full object-cover"
                        muted
                        loop
                        playsInline
                        onMouseEnter={e => (e.currentTarget as HTMLVideoElement).play().catch(() => {})}
                        onMouseLeave={e => { (e.currentTarget as HTMLVideoElement).pause(); (e.currentTarget as HTMLVideoElement).currentTime = 0; }}
                      />
                    ) : imgSrc ? (
                      <img
                        src={imgSrc}
                        className="w-full h-full object-cover"
                        alt=""
                      />
                    ) : (
                      <div className="flex flex-col items-center gap-1 text-slate-400">
                        <span className="text-3xl">{STATUS_ICONS[artwork.status] ?? '🎨'}</span>
                        <span className="text-xs capitalize">{artwork.status}</span>
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="p-3 space-y-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[artwork.status] ?? 'bg-slate-100 text-slate-500'}`}>
                        {artwork.status}
                      </span>
                      {artwork.hidden ? (
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-200 text-slate-500">hidden</span>
                      ) : null}
                    </div>
                    <p className="text-xs text-slate-400 truncate">{artwork.created_at?.slice(0, 10)}</p>

                    {/* Actions */}
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleToggleHide(artwork)}
                        disabled={pendingId === artwork.id}
                        className="flex-1 text-xs py-1.5 rounded-lg border border-slate-200 hover:border-pink-300 hover:text-pink-600 transition-colors disabled:opacity-40"
                      >
                        {artwork.hidden ? 'Show' : 'Hide'}
                      </button>
                      <button
                        onClick={() => handleDelete(artwork)}
                        disabled={pendingId === artwork.id}
                        className="flex-1 text-xs py-1.5 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-700',
  generating: 'bg-yellow-100 text-yellow-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-slate-100 text-slate-500',
};

export function AdminRoomPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const [artworks, setArtworks] = useState<AdminArtwork[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => {
    if (!roomId) return;
    getRoomArtworks(roomId)
      .then(setArtworks)
      .catch(() => navigate('/admin/login'))
      .finally(() => setLoading(false));
  }, [roomId, navigate]);

  const handleToggleHide = async (artwork: AdminArtwork) => {
    setPendingId(artwork.id);
    try {
      if (artwork.hidden) {
        await unhideArtwork(artwork.id);
      } else {
        await hideArtwork(artwork.id);
      }
      setArtworks(prev =>
        prev.map(a => a.id === artwork.id ? { ...a, hidden: artwork.hidden ? 0 : 1 } : a)
      );
    } finally {
      setPendingId(null);
    }
  };

  const handleDelete = async (artwork: AdminArtwork) => {
    if (!confirm(`Delete this artwork? This cannot be undone.`)) return;
    setPendingId(artwork.id);
    try {
      await deleteArtwork(artwork.id);
      setArtworks(prev => prev.filter(a => a.id !== artwork.id));
    } catch {
      alert('Failed to delete artwork.');
    } finally {
      setPendingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-rose-50 to-pink-100 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate('/admin/rooms')}
            className="text-sm text-slate-400 hover:text-pink-500 transition-colors"
          >
            ← Rooms
          </button>
          <h1 className="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-500 to-violet-500">
            {roomId}
          </h1>
          <span className="ml-auto text-sm text-slate-400">{artworks.length} items</span>
        </div>

        {loading ? (
          <p className="text-slate-400 text-center mt-16">Loading...</p>
        ) : artworks.length === 0 ? (
          <p className="text-slate-400 text-center mt-16">No artworks in this room.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {artworks.map(artwork => (
              <div
                key={artwork.id}
                className={`bg-white/80 backdrop-blur-xl rounded-2xl border overflow-hidden shadow transition-all ${artwork.hidden ? 'opacity-50 border-slate-200' : 'border-white/50'}`}
              >
                {/* Media Preview */}
                <div className="aspect-video bg-slate-100 relative overflow-hidden">
                  {artwork.video_url ? (
                    <video
                      src={resolveUrl(artwork.video_url)}
                      className="w-full h-full object-cover"
                      muted
                      loop
                      onMouseEnter={e => (e.currentTarget as HTMLVideoElement).play()}
                      onMouseLeave={e => { (e.currentTarget as HTMLVideoElement).pause(); (e.currentTarget as HTMLVideoElement).currentTime = 0; }}
                    />
                  ) : artwork.image_path ? (
                    <img
                      src={resolveUrl(artwork.image_path)}
                      className="w-full h-full object-cover"
                      alt=""
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-300 text-xs">No media</div>
                  )}
                </div>

                {/* Info */}
                <div className="p-3 space-y-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[artwork.status] ?? 'bg-slate-100 text-slate-500'}`}>
                      {artwork.status}
                    </span>
                    {artwork.hidden ? (
                      <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-200 text-slate-500">hidden</span>
                    ) : null}
                  </div>
                  <p className="text-xs text-slate-400 truncate">{artwork.created_at?.slice(0, 10)}</p>

                  {/* Actions */}
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => handleToggleHide(artwork)}
                      disabled={pendingId === artwork.id}
                      className="flex-1 text-xs py-1.5 rounded-lg border border-slate-200 hover:border-pink-300 hover:text-pink-600 transition-colors disabled:opacity-40"
                    >
                      {artwork.hidden ? 'Show' : 'Hide'}
                    </button>
                    <button
                      onClick={() => handleDelete(artwork)}
                      disabled={pendingId === artwork.id}
                      className="flex-1 text-xs py-1.5 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
