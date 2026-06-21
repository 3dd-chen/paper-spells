interface HeaderProps {
  spellCount: number;
  isLoaded: boolean;
  roomId?: string;
}

export function Header({ spellCount, isLoaded, roomId }: HeaderProps) {
  return (
    <div className="ui-container absolute top-0 left-0 w-full p-6 pointer-events-none flex justify-between items-start gap-4">
      <div className="pointer-events-auto">
        <h1 className="font-display text-[2.6rem] leading-[0.9] font-black tracking-tight text-ink">
          Paper <span className="italic text-vermilion">Spells</span>
        </h1>
        {roomId && (
          <div className="ps-chip tilt-r mt-2 inline-block bg-sun text-ink px-2.5 py-0.5 text-[0.62rem]">
            Room: {roomId}
          </div>
        )}
        <p className="font-label text-sm text-inksoft mt-2">
          {spellCount} {spellCount === 1 ? 'spell' : 'spells'} alive • Click to feed!
        </p>
      </div>

      <div className="pointer-events-auto flex items-center gap-2.5 bg-card border-2 border-ink rounded-xl px-4 py-2 shadow-pop-sm">
        <div
          style={{
            width: 11,
            height: 11,
            borderRadius: '50%',
            background: isLoaded ? '#f0411f' : '#a89f8e',
            border: '2px solid #1c1813',
            animation: isLoaded ? 'pulse 2s infinite' : 'none',
          }}
        />
        <span className="font-label font-bold text-xs tracking-wider text-ink">
          {isLoaded ? 'GALLERY LIVE' : 'LOADING...'}
        </span>
      </div>
    </div>
  );
}
