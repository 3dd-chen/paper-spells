interface HeaderProps {
  spellCount: number;
  isLoaded: boolean;
  roomId?: string;
}

export function Header({ spellCount, isLoaded, roomId }: HeaderProps) {
  return (
    <div className="ui-container absolute top-0 left-0 w-full p-6 pointer-events-none flex justify-between items-start">
      <div className="pointer-events-auto">
        <h1
          className="text-4xl font-extrabold tracking-tight"
          style={{
            background: 'linear-gradient(to right, #ec4899, #8b5cf6)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          Paper Spells
        </h1>
        {roomId && (
          <div className="mt-1 inline-block bg-pink-100 text-pink-600 px-2 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wider border border-pink-200">
            Room: {roomId}
          </div>
        )}
        <p style={{ color: '#9d174d', fontSize: 14, marginTop: 4, opacity: 0.8 }}>
          {spellCount} {spellCount === 1 ? 'spell' : 'spells'} alive • Click to feed!
        </p>
      </div>

      <div
        className="pointer-events-auto"
        style={{
          background: 'rgba(255,255,255,0.6)',
          backdropFilter: 'blur(12px)',
          border: '1.5px solid rgba(255,255,255,0.7)',
          borderRadius: '16px',
          padding: '8px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          boxShadow: '0 4px 16px rgba(236,72,153,0.1)',
        }}
      >
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: isLoaded ? '#ec4899' : '#d1d5db',
            boxShadow: isLoaded ? '0 0 6px #ec4899' : 'none',
            animation: isLoaded ? 'pulse 2s infinite' : 'none',
          }}
        />
        <span style={{ color: '#be185d', fontFamily: 'monospace', fontSize: 13, fontWeight: 600 }}>
          {isLoaded ? 'GALLERY LIVE' : 'LOADING...'}
        </span>
      </div>
    </div>
  );
}
