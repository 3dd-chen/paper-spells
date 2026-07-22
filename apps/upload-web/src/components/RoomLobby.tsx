import { useState, useMemo } from 'react';

export function RoomLobby() {
  const [roomCode, setRoomCode] = useState('');

  const stars = useMemo(() => {
    return Array.from({ length: 25 }).map((_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      size: Math.random() * 2.5 + 1,
      duration: `${Math.random() * 4 + 2}s`,
      delay: `${Math.random() * 5}s`,
    }));
  }, []);

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    if (roomCode.trim()) {
      window.location.search = `?room=${roomCode.trim()}`;
    }
  };

  return (
    <div className="cosmic-bg min-h-screen flex flex-col items-center justify-center p-6 text-white relative overflow-hidden">
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
      <div className="max-w-md w-full cosmic-card p-8 space-y-7 text-center relative">
        <span className="ps-chip tilt-l absolute -top-3 -left-2 bg-sun text-ink text-[0.62rem] px-3 py-1">
          Paper Spells
        </span>
        <h1 className="starwars-text text-[2.1rem] leading-[1.0] font-black tracking-wider">
          Enter Room
        </h1>
        <p className="text-sm text-white/70">
          Enter a room code to join the gallery and upload your spells.
        </p>
        <form onSubmit={handleJoin} className="space-y-4">
          <input
            type="text"
            value={roomCode}
            onChange={(e) => setRoomCode(e.target.value)}
            placeholder="Room Code (e.g. party-123)"
            className="ps-field w-full px-4 py-3.5 text-sm text-center"
            required
          />
          <button
            type="submit"
            className="ps-btn ps-btn-blue w-full flex items-center justify-center gap-2 py-4 px-6 text-white"
          >
            <span>Enter Room</span>
          </button>
        </form>
      </div>
    </div>
  );
}
