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

  if (!roomId) {
    return <RoomLobby />;
  }

  return (
    <div className="paper-bg min-h-screen flex flex-col items-center justify-center p-6 text-ink">
      <Toaster position="top-center" richColors />
      <div className="max-w-md w-full sticker p-8 space-y-8 relative">
        <span className="ps-chip tilt-r absolute -top-3 -right-2 bg-sun text-ink text-[0.62rem] px-3 py-1">
          Cast a spell
        </span>

        <div className="text-center space-y-2">
          <h1 className="font-display text-[2.7rem] leading-[0.95] font-black text-ink tracking-tight">
            Paper <span className="italic text-vermilion">Spells</span>
          </h1>
          <p className="text-sm text-inksoft">
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
