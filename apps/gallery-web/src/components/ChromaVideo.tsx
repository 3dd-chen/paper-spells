import { useEffect, useRef } from 'react';

interface ChromaVideoProps {
  src: string;
}

/**
 * Renders a video with real-time chroma-key (green screen + white background removal)
 * using a hidden <video> + a <canvas> that draws each frame with transparent pixels.
 *
 * Throttled to ~30 fps to keep CPU usage reasonable.
 */
export function ChromaVideo({ src }: ChromaVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    let animationId: number;
    let lastTime = 0;

    const render = (time: number) => {
      if (time - lastTime >= 33) { // ~30 fps
        lastTime = time;

        // Ensure video is playing (unlocks after first user gesture)
        if (video.paused && video.readyState >= 2) {
          video.play().catch(() => {});
        }

        if (video.readyState >= 2) {
          // Sync canvas dimensions to video (once)
          if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
          }

          ctx.drawImage(video, 0, 0);
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const data = imageData.data;

          for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];

            // 1. Green screen removal
            if (g - Math.max(r, b) > 30) {
              data[i + 3] = 0;
              continue;
            }
            // 2. Pure white background removal (fallback)
            if (r > 240 && g > 240 && b > 240) {
              data[i + 3] = 0;
            }
          }

          ctx.putImageData(imageData, 0, 0);
        }
      }

      animationId = requestAnimationFrame(render);
    };

    animationId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animationId);
  }, []);

  return (
    <div className="relative w-full h-full min-w-full min-h-full overflow-hidden">
      <video
        ref={videoRef}
        src={src}
        autoPlay
        loop
        muted
        playsInline
        crossOrigin="anonymous"
        style={{ display: 'none' }}
      />
      <canvas ref={canvasRef} style={{ display: 'block', position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain' }} />
    </div>
  );
}
