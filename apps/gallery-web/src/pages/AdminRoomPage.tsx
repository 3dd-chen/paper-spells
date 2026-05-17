import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getRoomArtworks, hideArtwork, unhideArtwork, deleteArtwork, type AdminArtwork } from '../lib/adminApi';
import { resolveVideoUrl } from '../lib/videoUrl';
import { ChromaVideo } from '../components/ChromaVideo';

// ── ChromaImage: canvas-based chroma key for static images ──────────────────
function ChromaImage({ src }: { src: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!src) return;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = src;
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      // Constrain to a reasonable preview size (never full resolution)
      const MAX = 512;
      const scale = Math.min(MAX / img.naturalWidth, MAX / img.naturalHeight, 1);
      canvas.width = Math.round(img.naturalWidth * scale);
      canvas.height = Math.round(img.naturalHeight * scale);
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      if (!ctx) return;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = imageData.data;
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i], g = d[i + 1], b = d[i + 2];
        if (g > 100 && g > r * 1.4 && g > b * 1.4) {
          d[i + 3] = 0;
        }
      }
      ctx.putImageData(imageData, 0, 0);
    };
    img.onerror = () => setFailed(true);
  }, [src]);

  if (failed) return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span className="text-slate-300 text-xs">Image error</span>
    </div>
  );

  return (
    // Absolute wrapper gives canvas a concrete width+height to compute % against
    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <canvas
        ref={canvasRef}
        style={{ maxWidth: '100%', maxHeight: '100%' }}
      />
    </div>
  );
}

// ── AdminRoomPage ────────────────────────────────────────────────────────────

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
      artwork.hidden ? await unhideArtwork(artwork.id) : await hideArtwork(artwork.id);
      setArtworks(prev =>
        prev.map(a => a.id === artwork.id ? { ...a, hidden: artwork.hidden ? 0 : 1 } : a)
      );
    } finally {
      setPendingId(null);
    }
  };

  const handleDelete = async (artwork: AdminArtwork) => {
    if (!confirm('Delete this artwork? This cannot be undone.')) return;
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
                  {/* Media Preview — checkered bg to show transparency */}
                  <div
                    className="aspect-video relative overflow-hidden flex items-center justify-center"
                    style={{
                      background: videoSrc || imgSrc
                        ? 'repeating-conic-gradient(#e2e8f0 0% 25%, #f8fafc 0% 50%) 0 0 / 16px 16px'
                        : '#f1f5f9',
                    }}
                  >
                    {videoSrc ? (
                      <ChromaVideo src={videoSrc} />
                    ) : imgSrc ? (
                      <ChromaImage src={imgSrc} />
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
                      {artwork.hidden
                        ? <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-200 text-slate-500">hidden</span>
                        : null}
                    </div>
                    <p className="text-xs text-slate-400 truncate">{artwork.created_at?.slice(0, 10)}</p>

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
