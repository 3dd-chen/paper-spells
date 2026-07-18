import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getRoomArtworks, hideArtwork, unhideArtwork, deleteArtwork, pollRoomArtworks, type AdminArtwork } from '../lib/adminApi';
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
        // 1. Green removal
        if (g > 100 && g > r * 1.4 && g > b * 1.4) {
          d[i + 3] = 0;
          continue;
        }
        // 2. White background removal (fallback)
        if (r > 240 && g > 240 && b > 240) {
          d[i + 3] = 0;
          continue;
        }
        // Smart inversion: Only invert dark sketch lines to white.
        // Keep bright highlights (neon glow, white space helmet) untouched.
        const brightness = Math.max(r, g, b);
        if (brightness < 100) {
          d[i] = 255 - r;
          d[i + 1] = 255 - g;
          d[i + 2] = 255 - b;
        }
      }
      ctx.putImageData(imageData, 0, 0);
    };
    img.onerror = () => setFailed(true);
  }, [src]);

  if (failed) return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span className="font-label text-white/60 text-xs">Image error</span>
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
  completed: 'bg-cobalt text-white border-white/20',
  generating: 'bg-sun text-ink border-white/20',
  failed: 'bg-vermilion text-white border-white/20',
  pending: 'bg-white/10 text-white/60 border-white/20',
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
      <svg {...common} stroke="#ffc23c" aria-hidden="true">
        <path d="M12 3a9 9 0 1 0 9 9" />
        <path d="M12 7v5l3 2" />
      </svg>
    );
  }
  if (status === 'pending') {
    return (
      <svg {...common} stroke="rgba(255, 255, 255, 0.6)" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
    );
  }
  // default / unknown — framed canvas glyph
  return (
    <svg {...common} stroke="rgba(255, 255, 255, 0.6)" aria-hidden="true">
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
  const [refreshing, setRefreshing] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 12;

  const totalPages = Math.ceil(artworks.length / ITEMS_PER_PAGE);

  useEffect(() => {
    if (currentPage > totalPages && totalPages > 0) {
      setCurrentPage(totalPages);
    }
  }, [artworks.length, totalPages, currentPage]);

  const paginatedArtworks = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return artworks.slice(start, start + ITEMS_PER_PAGE);
  }, [artworks, currentPage]);

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

  const fetchArtworks = useCallback(async () => {
    if (!roomId) return;
    try {
      const data = await getRoomArtworks(roomId);
      setArtworks(data);
    } catch {
      navigate('/admin/login');
    }
  }, [roomId, navigate]);

  // Background polling: If there are any pending/generating artworks,
  // trigger status checks in the background every 10 seconds.
  useEffect(() => {
    if (!roomId) return;
    const hasGenerating = artworks.some(a => a.status === 'generating' || a.status === 'pending');
    if (!hasGenerating) return;

    const interval = setInterval(async () => {
      try {
        await pollRoomArtworks(roomId);
        await fetchArtworks();
      } catch (err) {
        console.error('Background admin poll failed:', err);
      }
    }, 10000); // 10s interval

    return () => clearInterval(interval);
  }, [roomId, artworks, fetchArtworks]);

  useEffect(() => {
    setCurrentPage(1);
    setLoading(true);
    fetchArtworks().finally(() => setLoading(false));
  }, [fetchArtworks]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchArtworks();
    setRefreshing(false);
  };

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
    <div className="cosmic-bg min-h-screen p-6 text-white relative overflow-x-hidden">
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
      <div className="max-w-5xl mx-auto relative z-10">
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate('/admin/rooms')}
            className="font-label text-sm text-white/60 hover:text-vermilion transition-colors"
          >
            ← Rooms
          </button>
          <h1 className="starwars-text text-[2.0rem] leading-[1.0] font-black tracking-wider">
            {roomId}
          </h1>
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={refreshing || loading}
              className="ps-btn py-1.5 px-3 text-xs bg-white/5 hover:bg-white/10 border border-white/10 rounded flex items-center gap-1.5 font-label transition-all cursor-pointer disabled:opacity-50"
            >
              {refreshing ? (
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
              )}
              <span>Reload</span>
            </button>
            <span className="font-label text-sm text-white/60">{artworks.length} items</span>
          </div>
        </div>

        {loading ? (
          <p className="font-label text-white/60 text-center mt-16">Loading...</p>
        ) : artworks.length === 0 ? (
          <p className="font-label text-white/60 text-center mt-16">No artworks in this room.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {paginatedArtworks.map(artwork => {
                const videoSrc = artwork.video_url ? resolveVideoUrl(artwork.video_url) : null;
                const imgSrc = artwork.image_path ? resolveVideoUrl(artwork.image_path) : null;

                return (
                  <div
                    key={artwork.id}
                    className={`cosmic-card border border-white/10 overflow-hidden transition-all ${artwork.hidden ? 'opacity-40' : ''}`}
                  >
                    {/* Media Preview — cosmic space background to match frontend */}
                    <div
                      className="aspect-video relative overflow-hidden flex items-center justify-center border-b border-white/10 cosmic-bg"
                    >
                      {videoSrc ? (
                        <ChromaVideo src={videoSrc} />
                      ) : imgSrc ? (
                        <ChromaImage src={imgSrc} />
                      ) : (
                        <div className="flex flex-col items-center gap-1.5 text-white/60">
                          <StatusGlyph status={artwork.status} />
                          <span className="font-label text-xs capitalize">{artwork.status}</span>
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="p-3 space-y-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={`font-label text-[0.65rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border border-white/10 ${STATUS_COLORS[artwork.status] ?? 'bg-white/10 text-white/60'}`}>
                          {artwork.status}
                        </span>
                        {artwork.hidden
                          ? <span className="font-label text-[0.65rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-white/40">hidden</span>
                          : null}
                      </div>
                      <p className="font-label text-xs text-white/50 truncate">{artwork.created_at?.slice(0, 10)}</p>

                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={() => handleToggleHide(artwork)}
                          disabled={pendingId === artwork.id}
                          className="font-label font-bold flex-1 text-xs py-1.5 rounded-lg border border-white/20 text-white hover:bg-white hover:text-black transition-colors disabled:opacity-40"
                        >
                          {artwork.hidden ? 'Show' : 'Hide'}
                        </button>
                        <button
                          onClick={() => handleDelete(artwork)}
                          disabled={pendingId === artwork.id}
                          className="font-label font-bold flex-1 text-xs py-1.5 rounded-lg border border-vermilion text-vermilion hover:bg-vermilion hover:text-white transition-colors disabled:opacity-40"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-8 pt-4 border-t border-white/10 font-label">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                  disabled={currentPage === 1}
                  className="ps-btn py-1.5 px-4 bg-white/5 hover:bg-white/10 disabled:opacity-30 border border-white/10 rounded cursor-pointer disabled:cursor-not-allowed transition-all"
                >
                  Previous
                </button>
                <span className="text-sm text-white/60">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                  disabled={currentPage === totalPages}
                  className="ps-btn py-1.5 px-4 bg-white/5 hover:bg-white/10 disabled:opacity-30 border border-white/10 rounded cursor-pointer disabled:cursor-not-allowed transition-all"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
