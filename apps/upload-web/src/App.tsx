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
    <div className="min-h-screen bg-gradient-to-b from-rose-50 to-pink-100 flex flex-col items-center justify-center p-6 text-slate-800">
      <Toaster position="top-center" richColors />
      <div className="max-w-md w-full bg-white/80 backdrop-blur-xl rounded-3xl shadow-xl border border-white/50 p-8 space-y-8">

        <div className="text-center space-y-2">
          <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-500 to-violet-500 tracking-tight">
            Paper Spells
          </h1>
          <p className="text-sm text-slate-500">
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
              className="w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-pink-500 to-violet-500 text-white font-semibold py-4 px-6 rounded-2xl shadow-lg shadow-pink-200 hover:shadow-pink-300 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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
