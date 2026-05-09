import { useState, useRef, type ChangeEvent } from 'react';
import { Upload, Camera, Loader2, CheckCircle2 } from 'lucide-react';

export default function App() {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [processedImage, setProcessedImage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processCanvasThreshold = (src: string): Promise<string> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        if (!ctx) return reject('Canvas context not available');

        ctx.drawImage(img, 0, 0);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;

        // Convert bright pixels (white paper) to #00FF00 (pure green)
        for (let i = 0; i < data.length; i += 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          
          const brightness = (r + g + b) / 3;
          if (brightness > 160) { // Threshold for white/off-white paper
            data[i] = 0;       // R
            data[i + 1] = 255; // G
            data[i + 2] = 0;   // B
          } else {
             // Enhance dark lines
             data[i] = 0;
             data[i + 1] = 0;
             data[i + 2] = 0;
          }
        }
        ctx.putImageData(imageData, 0, 0);
        resolve(canvas.toDataURL('image/png'));
      };
      img.onerror = reject;
      img.src = src;
    });
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);
    const reader = new FileReader();
    reader.onload = async (event) => {
      const src = event.target?.result as string;
      setImageSrc(src);
      try {
        const result = await processCanvasThreshold(src);
        setProcessedImage(result);
      } catch (err) {
        console.error("Error processing image:", err);
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
      // In a real scenario, this connects to our FastAPI backend
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_data: processedImage })
      });
      if (res.ok) {
        const data = await res.json();
        setTaskId(data.task_id);
      } else {
        console.error("Upload failed");
      }
    } catch (err) {
      console.error("Network error:", err);
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

        {taskId ? (
          <div className="flex flex-col items-center justify-center space-y-4 py-12">
            <div className="w-16 h-16 bg-green-100 text-green-500 rounded-full flex items-center justify-center">
              <CheckCircle2 size={32} />
            </div>
            <p className="font-medium text-lg">Artwork Uploaded!</p>
            <p className="text-sm text-slate-500">Wait for it to appear in the gallery.</p>
          </div>
        ) : (
          <>
            <div 
              onClick={() => fileInputRef.current?.click()}
              className="relative group cursor-pointer border-2 border-dashed border-pink-200 rounded-2xl hover:border-pink-400 hover:bg-pink-50/50 transition-all aspect-[4/3] flex flex-col items-center justify-center overflow-hidden"
            >
              <input 
                type="file" 
                accept="image/*" 
                capture="environment"
                className="hidden" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
              />
              
              {isProcessing ? (
                <div className="flex flex-col items-center space-y-2 text-pink-500">
                  <Loader2 className="animate-spin" size={32} />
                  <span className="text-sm font-medium">Processing ink...</span>
                </div>
              ) : processedImage ? (
                <img src={processedImage} alt="Processed" className="w-full h-full object-contain bg-white" />
              ) : imageSrc ? (
                <img src={imageSrc} alt="Original" className="w-full h-full object-contain opacity-50" />
              ) : (
                <div className="flex flex-col items-center space-y-4 text-pink-400 group-hover:text-pink-500 transition-colors">
                  <Camera size={48} strokeWidth={1.5} />
                  <span className="text-sm font-medium">Tap to snap your doodle</span>
                </div>
              )}
            </div>

            <button
              onClick={handleUpload}
              disabled={!processedImage || isUploading}
              className="w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-pink-500 to-violet-500 text-white font-semibold py-4 px-6 rounded-2xl shadow-lg shadow-pink-200 hover:shadow-pink-300 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUploading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <Upload size={20} />
              )}
              <span>{isUploading ? 'Magic happens...' : 'Animate It!'}</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
}
