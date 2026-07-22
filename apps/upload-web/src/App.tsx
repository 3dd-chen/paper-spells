import { useMemo } from 'react';
import { Upload, Loader2 } from 'lucide-react';
import { Toaster } from 'sonner';
import { UploadZone } from './components/UploadZone';
import { SuccessScreen } from './components/SuccessScreen';
import { RoomLobby } from './components/RoomLobby';
import { useArtworkUpload } from './hooks/useArtworkUpload';

export default function App() {
  const { status, imageSrc, processedImage, handleFileSelect, handleUpload } = useArtworkUpload();

  const isProcessing = status === 'processing';
  const isUploading = status === 'uploading';
  const isSubmitted = status === 'success';

  const roomId = new URLSearchParams(window.location.search).get('room');

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

  if (!roomId) {
    return <RoomLobby />;
  }

  return (
    <div className="cosmic-bg min-h-screen flex flex-col items-center justify-center p-6 text-white relative overflow-hidden">
      <Toaster position="top-center" richColors />
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
      <div className="max-w-md w-full cosmic-card p-8 space-y-8 relative">
        <span className="ps-chip tilt-r absolute -top-3 -right-2 bg-sun text-ink text-[0.62rem] px-3 py-1">
          Cast a spell
        </span>

        <div className="text-center space-y-2">
          <h1 className="starwars-text text-[2.1rem] leading-[1.0] font-black tracking-wider">
            Paper Spells
          </h1>
          <p className="text-sm text-white/70">
            Upload your paper drawing and watch it come alive!
          </p>
        </div>

        {isSubmitted ? (
          <SuccessScreen />
        ) : (
          <>
            <UploadZone
              imageSrc={imageSrc}
              isProcessing={isProcessing}
              onFileSelect={handleFileSelect}
            />
            <button
              onClick={handleUpload}
              disabled={!processedImage || isUploading}
              className="ps-btn ps-btn-blue w-full flex items-center justify-center gap-2 py-4 px-6 text-base"
            >
              {isUploading ? <Loader2 className="animate-spin" size={20} /> : <Upload size={20} />}
              <span>{isUploading ? 'Magic happens...' : 'Animate It!'}</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
}
