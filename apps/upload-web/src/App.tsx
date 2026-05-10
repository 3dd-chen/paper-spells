import { useState, type ChangeEvent } from 'react';
import { Upload, Loader2 } from 'lucide-react';
import { UploadZone } from './components/UploadZone';
import { SuccessScreen } from './components/SuccessScreen';
import { processImageForUpload } from './hooks/useImageProcessor';
import { submitArtwork } from './lib/api';

export default function App() {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [processedImage, setProcessedImage] = useState<string | null>(null);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);
    const reader = new FileReader();
    reader.onload = async (event) => {
      const src = event.target?.result as string;
      setImageSrc(src);
      try {
        const result = await processImageForUpload(src);
        setProcessedImage(result.dataUrl);
        setAspectRatio(result.aspectRatio);
      } catch (err) {
        console.error('Error processing image:', err);
      } finally {
        setIsProcessing(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleUpload = async () => {
    if (!processedImage) return;
    setIsUploading(true);
    try {
      await submitArtwork(processedImage, aspectRatio);
      setIsSubmitted(true);
    } catch (err) {
      console.error('Upload error:', err);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-rose-50 to-pink-100 flex flex-col items-center justify-center p-6 text-slate-800">
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
