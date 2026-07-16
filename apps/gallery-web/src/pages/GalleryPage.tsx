import { useState, useMemo } from 'react';
import { useGalleryPolling } from '../hooks/useGalleryPolling';
import { usePhysicsEngine } from '../hooks/usePhysicsEngine';
import { ChromaVideo } from '../components/ChromaVideo';
import { Header } from '../components/Header';
import { RoomLobby } from '../components/RoomLobby';
import { resolveVideoUrl } from '../lib/videoUrl';

export function GalleryPage() {
  const roomId = new URLSearchParams(window.location.search).get('room');

  const { videos, isLoaded, error } = useGalleryPolling();
  const [food, setFood] = useState<{ x: number; y: number; id: number } | null>(null);
  const { instancesRef, foodRef, initInstance } = usePhysicsEngine(() => setFood(null));

  const stars = useMemo(() => {
    return Array.from({ length: 40 }).map((_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      size: Math.random() * 3 + 1, // 1px to 4px
      duration: `${Math.random() * 4 + 2}s`, // 2s to 6s
      delay: `${Math.random() * 5}s`,
    }));
  }, []);

  const handleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.ui-container')) return;

    const x = e.clientX;
    const y = e.clientY;
    foodRef.current = { x, y, active: true, timer: 0 };
    setFood({ x, y, id: Date.now() });

    document.querySelectorAll('video').forEach((v) =>
      v.play().catch(() => {}),
    );
  };

  if (!roomId) {
    return <RoomLobby />;
  }

  return (
    <div
      className="cosmic-bg relative min-h-screen w-full overflow-hidden cursor-crosshair"
      onClick={handleClick}
    >
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
            boxShadow: star.size > 2.5 ? '0 0 8px rgba(255, 255, 255, 0.8)' : 'none',
          } as React.CSSProperties}
        />
      ))}
      {food && (
        <div
          key={food.id}
          style={{
            position: 'absolute',
            left: food.x,
            top: food.y,
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
            zIndex: 100,
            animation: 'pop 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
          }}
        >
          <svg width="42" height="42" viewBox="0 0 32 32" aria-hidden="true">
            <path
              d="M16 2 Q17.5 14.5 30 16 Q17.5 17.5 16 30 Q14.5 17.5 2 16 Q14.5 14.5 16 2 Z"
              fill="#ffc23c"
              stroke="#1c1813"
              strokeWidth="2"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}

      {videos.map((v) => {
        initInstance(v.id, v.facing_direction ?? undefined);
        return (
          <div
            key={v.id}
            ref={(el) => {
              const inst = instancesRef.current[v.id];
              if (inst) inst.element = el;
            }}
            className="absolute top-0 left-0 w-[320px] aspect-video will-change-transform pointer-events-none overflow-hidden"
          >
            <ChromaVideo src={resolveVideoUrl(v.video_url ?? '')} />
          </div>
        );
      })}

      {isLoaded && !error && videos.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="sticker tilt-l px-16 py-12 text-center">
            <svg width="60" height="60" viewBox="0 0 32 32" className="mb-4 animate-bob inline-block" aria-hidden="true">
              <path
                d="M16 2 Q17.5 14.5 30 16 Q17.5 17.5 16 30 Q14.5 17.5 2 16 Q14.5 14.5 16 2 Z"
                fill="#2f4fe6"
                stroke="#1c1813"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
            </svg>
            <p className="font-display font-black text-2xl text-ink">
              No spells cast yet...
            </p>
            <p className="text-sm text-inksoft mt-2">
              Upload a drawing to see it come alive here!
            </p>
          </div>
        </div>
      )}

      <Header spellCount={videos.length} isLoaded={isLoaded} roomId={roomId} />
    </div>
  );
}
