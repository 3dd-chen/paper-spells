import { useState } from 'react';
import type { ChangeEvent } from 'react';
import { processImageForUpload } from './useImageProcessor';
import { submitArtwork, analyzeDirection } from '../lib/api';
import { toast } from 'sonner';

export function useArtworkUpload() {
  const [status, setStatus] = useState<'idle' | 'processing' | 'uploading' | 'success'>('idle');
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [processedImage, setProcessedImage] = useState<string | null>(null);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [originalDirection, setOriginalDirection] = useState('right');
  const [characterDescription, setCharacterDescription] = useState('a simple black stick figure');
  
  const roomId = new URLSearchParams(window.location.search).get('room');

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus('processing');
    const reader = new FileReader();
    reader.onload = async (event) => {
      const src = event.target?.result as string;
      setImageSrc(src);
      try {
        // 1. Analyze direction and description
        const analysis = await analyzeDirection(src);
        setOriginalDirection(analysis.direction);
        if (analysis.description) {
          setCharacterDescription(analysis.description);
        }
        
        // 2. Process and flip horizontally if the character is facing left
        const flipHorizontal = analysis.direction === 'left';
        const result = await processImageForUpload(src, flipHorizontal);
        
        setProcessedImage(result.dataUrl);
        setAspectRatio(result.aspectRatio);
        setStatus('idle');
      } catch (err: unknown) {
        console.error('Error processing image:', err);
        const errMsg = err instanceof Error ? err.message : 'Unknown error';
        toast.error(`Failed to process image: ${errMsg}`);
        setStatus('idle');
      }
    };
    reader.onerror = () => {
      toast.error('Failed to read file');
      setStatus('idle');
    };
    reader.readAsDataURL(file);
  };

  const handleUpload = async () => {
    if (!processedImage || !roomId) return;
    setStatus('uploading');
    try {
      await submitArtwork(processedImage, aspectRatio, roomId, originalDirection, characterDescription);
      setStatus('success');
      toast.success('Artwork animated successfully!');
    } catch (err: unknown) {
      console.error('Upload error:', err);
      const errMsg = err instanceof Error ? err.message : 'Unknown error';
      toast.error(`Failed to upload artwork: ${errMsg}`);
      setStatus('idle');
    }
  };

  return { status, imageSrc, processedImage, handleFileSelect, handleUpload };
}
