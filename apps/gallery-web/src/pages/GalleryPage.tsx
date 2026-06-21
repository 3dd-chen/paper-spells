import { useState } from 'react';
import { useGalleryPolling } from '../hooks/useGalleryPolling';
import { usePhysicsEngine } from '../hooks/usePhysicsEngine';
import { ChromaVideo } from '../components/ChromaVideo';
import { Header } from '../components/Header';
import { RoomLobby } from '../components/RoomLobby';
import { resolveVideoUrl } from '../lib/videoUrl';

export function GalleryPage() {
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

    document.querySelectorAll('video').forEach((v) =>
      v.play().catch(() => {}),
    );
  };

  if (!roomId) {
    return <RoomLobby />;
  }

  return (
    <div
      className="paper-bg relative min-h-screen w-full overflow-hidden cursor-crosshair"
      onClick={handleClick}
    >
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
            className="absolute top-0 left-0 w-[320px] aspect-video will-change-transform pointer-events-none overflow-hidden"
          >
            <ChromaVideo src={resolveVideoUrl(v.video_url ?? '')} />
          </div>
        );
      })}

      {isLoaded && videos.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="sticker tilt-l px-16 py-12 text-center">
            <div className="text-5xl mb-3 animate-bob inline-block">🪄</div>
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
