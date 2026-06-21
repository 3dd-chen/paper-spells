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
      <span className="font-label text-inksoft text-xs">Image error</span>
    </div>
  );

  return (
    <canvas
      ref={canvasRef}
      style={{ display: 'block', position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain' }}
    />
  );
}

// ── AdminRoomPage ────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-cobalt text-white border-ink',
  generating: 'bg-sun text-ink border-ink',
  failed: 'bg-vermilion text-white border-ink',
  pending: 'bg-paper-deep text-inksoft border-ink',
};

// Inline ink glyphs (no emoji) keyed by artwork status.
function StatusGlyph({ status }: { status: string }) {
  const common = {
    width: 30,
    height: 30,
    viewBox: '0 0 24 24',
    fill: 'none',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  if (status === 'failed') {
    return (
      <svg {...common} stroke="#f0411f" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M9 9l6 6M15 9l-6 6" />
      </svg>
    );
  }
  if (status === 'generating') {
    return (
      <svg {...common} stroke="#1c1813" aria-hidden="true">
        <path d="M12 3a9 9 0 1 0 9 9" />
        <path d="M12 7v5l3 2" />
      </svg>
    );
  }
  if (status === 'pending') {
    return (
      <svg {...common} stroke="#6a6155" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
    );
  }
  // default / unknown — framed canvas glyph
  return (
    <svg {...common} stroke="#6a6155" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2.5" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="M21 15l-5-5L5 21" />
    </svg>
  );
}

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
    <div className="paper-bg min-h-screen p-6 text-ink">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate('/admin/rooms')}
            className="font-label text-sm text-inksoft hover:text-vermilion transition-colors"
          >
            ← Rooms
          </button>
          <h1 className="font-display text-3xl font-black text-ink">
            {roomId}
          </h1>
          <span className="ml-auto font-label text-sm text-inksoft">{artworks.length} items</span>
        </div>

        {loading ? (
          <p className="font-label text-inksoft text-center mt-16">Loading...</p>
        ) : artworks.length === 0 ? (
          <p className="font-label text-inksoft text-center mt-16">No artworks in this room.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {artworks.map(artwork => {
              const videoSrc = artwork.video_url ? resolveVideoUrl(artwork.video_url) : null;
              const imgSrc = artwork.image_path ? resolveVideoUrl(artwork.image_path) : null;

              return (
                <div
                  key={artwork.id}
                  className={`bg-card border-2 border-ink rounded-2xl overflow-hidden shadow-pop transition-all ${artwork.hidden ? 'opacity-50' : ''}`}
                >
                  {/* Media Preview — checkered bg to show transparency */}
                  <div
                    className="aspect-video relative overflow-hidden flex items-center justify-center border-b-2 border-ink"
                    style={{
                      background: videoSrc || imgSrc
                        ? 'repeating-conic-gradient(#e6dcc6 0% 25%, #fbf7ec 0% 50%) 0 0 / 16px 16px'
                        : '#e6dcc6',
                    }}
                  >
                    {videoSrc ? (
                      <ChromaVideo src={videoSrc} />
                    ) : imgSrc ? (
                      <ChromaImage src={imgSrc} />
                    ) : (
                      <div className="flex flex-col items-center gap-1.5 text-inksoft">
                        <StatusGlyph status={artwork.status} />
                        <span className="font-label text-xs capitalize">{artwork.status}</span>
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="p-3 space-y-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`font-label text-[0.65rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border-2 ${STATUS_COLORS[artwork.status] ?? 'bg-paper-deep text-inksoft border-ink'}`}>
                        {artwork.status}
                      </span>
                      {artwork.hidden
                        ? <span className="font-label text-[0.65rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border-2 border-ink bg-paper-deep text-inksoft">hidden</span>
                        : null}
                    </div>
                    <p className="font-label text-xs text-inksoft truncate">{artwork.created_at?.slice(0, 10)}</p>

                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleToggleHide(artwork)}
                        disabled={pendingId === artwork.id}
                        className="font-label font-bold flex-1 text-xs py-1.5 rounded-lg border-2 border-ink hover:bg-ink hover:text-paper transition-colors disabled:opacity-40"
                      >
                        {artwork.hidden ? 'Show' : 'Hide'}
                      </button>
                      <button
                        onClick={() => handleDelete(artwork)}
                        disabled={pendingId === artwork.id}
                        className="font-label font-bold flex-1 text-xs py-1.5 rounded-lg border-2 border-vermilion text-vermilion hover:bg-vermilion hover:text-white transition-colors disabled:opacity-40"
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
