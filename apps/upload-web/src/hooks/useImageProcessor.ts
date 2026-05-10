/**
 * Processes a raw image:
 *  1. Detects orientation (portrait → 9:16, landscape → 16:9)
 *  2. Pads to the correct aspect ratio with a pure green (#00FF00) background
 *  3. Converts the bright white paper pixels to the same green (chroma key)
 *  4. Returns the processed data URL and the detected aspect ratio
 */
export function processImageForUpload(
  src: string,
): Promise<{ dataUrl: string; aspectRatio: string }> {
  return new Promise((resolve, reject) => {
    const img = new Image();

    img.onload = () => {
      const isVertical = img.width < img.height;
      const targetAspectRatio = isVertical ? '9:16' : '16:9';
      const targetRatioNum = isVertical ? 9 / 16 : 16 / 9;

      let targetWidth: number;
      let targetHeight: number;
      let xOffset = 0;
      let yOffset = 0;

      if (img.width / img.height < targetRatioNum) {
        // Image is narrower than target — pad left/right
        targetHeight = img.height;
        targetWidth = img.height * targetRatioNum;
        xOffset = (targetWidth - img.width) / 2;
      } else {
        // Image is wider than target — pad top/bottom
        targetWidth = img.width;
        targetHeight = img.width / targetRatioNum;
        yOffset = (targetHeight - img.height) / 2;
      }

      const canvas = document.createElement('canvas');
      canvas.width = targetWidth;
      canvas.height = targetHeight;

      const ctx = canvas.getContext('2d');
      if (!ctx) return reject(new Error('Canvas context not available'));

      // Fill with pure green (chroma key background for padding)
      ctx.fillStyle = '#00FF00';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, xOffset, yOffset);

      // Convert bright pixels (white paper) to pure green
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      const BRIGHTNESS_THRESHOLD = 160;

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        // Skip pixels already green (padding)
        if (r === 0 && g === 255 && b === 0) continue;

        const brightness = (r + g + b) / 3;
        if (brightness > BRIGHTNESS_THRESHOLD) {
          data[i]     = 0;
          data[i + 1] = 255;
          data[i + 2] = 0;
        } else {
          data[i]     = 0;
          data[i + 1] = 0;
          data[i + 2] = 0;
        }
      }

      ctx.putImageData(imageData, 0, 0);
      resolve({ dataUrl: canvas.toDataURL('image/png'), aspectRatio: targetAspectRatio });
    };

    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = src;
  });
}
