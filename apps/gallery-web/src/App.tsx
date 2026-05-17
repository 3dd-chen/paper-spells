import { useState } from 'react';
import { useGalleryPolling } from './hooks/useGalleryPolling';
import { usePhysicsEngine } from './hooks/usePhysicsEngine';
import { ChromaVideo } from './components/ChromaVideo';
import { Header } from './components/Header';
import { RoomLobby } from './components/RoomLobby';
import { resolveVideoUrl } from './lib/videoUrl';

export default function App() {
  const roomId = new URLSearchParams(window.location.search).get('room');
  
  const { videos, isLoaded } = useGalleryPolling();
  const [food, setFood] = useState<{ x: number; y: number; id: number } | null>(null);
  const { instancesRef, foodRef, initInstance } = usePhysicsEngine(() => setFood(null));

  const handleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.ui-container')) return;

    const x = e.clientX;
    const y = e.clientY;
    foodRef.current = { x, y, active: true, timer: 0 };
    setFood({ x, y, id: Date.now() });

    // Unlock video autoplay on first user gesture
    document.querySelectorAll('video').forEach((v) =>
      v.play().catch(() => {}),
    );
  };

  if (!roomId) {
    return <RoomLobby />;
  }

  return (
    <div
      className="relative min-h-screen w-full overflow-hidden bg-gradient-to-b from-rose-50 to-pink-100 cursor-crosshair"
      onClick={handleClick}
    >
      {/* Food emoji */}
      {food && (
        <div
          key={food.id}
          style={{
            position: 'absolute',
            left: food.x,
            top: food.y,
            transform: 'translate(-50%, -50%)',
            fontSize: 40,
            pointerEvents: 'none',
            zIndex: 100,
            animation: 'pop 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
          }}
        >
          🧁
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
            className="absolute top-0 left-0 w-[220px] will-change-transform pointer-events-none overflow-hidden"
          >
            <ChromaVideo src={resolveVideoUrl(v.video_url ?? '')} />
          </div>
        );
      })}

      {/* Empty state */}
      {isLoaded && videos.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div
            style={{
              background: 'rgba(255,255,255,0.7)',
              backdropFilter: 'blur(16px)',
              borderRadius: '24px',
              border: '1.5px solid rgba(255,255,255,0.6)',
              boxShadow: '0 8px 32px rgba(236,72,153,0.12)',
              padding: '48px 64px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 12 }}>🪄</div>
            <p style={{ color: '#be185d', fontWeight: 600, fontSize: 18 }}>
              No spells cast yet...
            </p>
            <p style={{ color: '#9d174d', fontSize: 14, marginTop: 8, opacity: 0.7 }}>
              Upload a drawing to see it come alive here!
            </p>
          </div>
        </div>
      )}

      <Header spellCount={videos.length} isLoaded={isLoaded} roomId={roomId} />
    </div>
  );
}