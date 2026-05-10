import { useRef, type ChangeEvent } from 'react';
import { Camera, Loader2 } from 'lucide-react';

interface UploadZoneProps {
  imageSrc: string | null;
  isProcessing: boolean;
  onFileSelect: (e: ChangeEvent<HTMLInputElement>) => void;
}

/**
 * Tap/click area to select a photo.
 * Shows the original (unprocessed) image as preview so the user
 * always sees their actual drawing, not the green-screen version.
 */
export function UploadZone({ imageSrc, isProcessing, onFileSelect }: UploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
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
        onChange={onFileSelect}
      />

      {isProcessing ? (
        <div className="flex flex-col items-center space-y-2 text-pink-500">
          <Loader2 className="animate-spin" size={32} />
          <span className="text-sm font-medium">Processing ink...</span>
        </div>
      ) : imageSrc ? (
        <img src={imageSrc} alt="Preview" className="w-full h-full object-contain" />
      ) : (
        <div className="flex flex-col items-center space-y-4 text-pink-400 group-hover:text-pink-500 transition-colors">
          <Camera size={48} strokeWidth={1.5} />
          <span className="text-sm font-medium">Tap to snap your doodle</span>
        </div>
      )}
    </div>
  );
}
