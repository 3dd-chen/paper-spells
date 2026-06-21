import { useState } from 'react';

export function RoomLobby() {
  const [roomCode, setRoomCode] = useState('');

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    if (roomCode.trim()) {
      window.location.search = `?room=${roomCode.trim()}`;
    }
  };

  return (
    <div className="paper-bg min-h-screen flex flex-col items-center justify-center p-6 text-ink">
      <div className="max-w-md w-full sticker p-8 space-y-7 text-center relative">
        <span className="ps-chip tilt-l absolute -top-3 -left-2 bg-cobalt text-white text-[0.62rem] px-3 py-1">
          Paper Spells
        </span>
        <h1 className="font-display text-[2.7rem] leading-[0.95] font-black text-ink tracking-tight">
          Enter <span className="italic text-cobalt">Room</span>
        </h1>
        <p className="text-sm text-inksoft">
          Enter a room code to join the gallery and view the spells.
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
            className="ps-btn ps-btn-ink w-full flex items-center justify-center gap-2 py-4 px-6"
          >
            <span>Enter Room</span>
          </button>
        </form>
      </div>
    </div>
  );
}
