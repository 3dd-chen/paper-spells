/**
 * Processes a raw image using a Web Worker (OffscreenCanvas) for performance.
 * 
 *  1. Detects orientation (portrait → 9:16, landscape → 16:9)
 *  2. Pads to the correct aspect ratio with a pure green (#00FF00) background
 *  3. Converts the bright white paper pixels to the same green (chroma key)
 *  4. Returns the processed data URL and the detected aspect ratio
 */
export function processImageForUpload(
  src: string,
  flipHorizontal: boolean = false,
): Promise<{ dataUrl: string; aspectRatio: string }> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('../workers/imageProcessor.worker.ts', import.meta.url), { type: 'module' });

    worker.onmessage = (e) => {
      if (e.data.type === 'success') {
        resolve({ dataUrl: e.data.dataUrl, aspectRatio: e.data.aspectRatio });
      } else {
        reject(new Error(e.data.error));
      }
      worker.terminate();
    };

    worker.onerror = (err) => {
      reject(new Error(err.message));
      worker.terminate();
    };

    worker.postMessage({ src, flipHorizontal });
  });
}
