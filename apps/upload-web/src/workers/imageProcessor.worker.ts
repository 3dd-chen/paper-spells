self.onmessage = async (e: MessageEvent<{ src: string }>) => {
  const { src } = e.data;

  try {
    // 1. Fetch the image to get a Blob
    const response = await fetch(src);
    const blob = await response.blob();
    
    // 2. Convert Blob to ImageBitmap (Web Worker safe)
    const img = await createImageBitmap(blob);

    const isVertical = img.width < img.height;
    const targetAspectRatio = isVertical ? '9:16' : '16:9';
    const targetRatioNum = isVertical ? 9 / 16 : 16 / 9;

    let targetWidth: number;
    let targetHeight: number;
    let xOffset = 0;
    let yOffset = 0;

    if (img.width / img.height < targetRatioNum) {
      targetHeight = img.height;
      targetWidth = img.height * targetRatioNum;
      xOffset = (targetWidth - img.width) / 2;
    } else {
      targetWidth = img.width;
      targetHeight = img.width / targetRatioNum;
      yOffset = (targetHeight - img.height) / 2;
    }

    // 3. Use OffscreenCanvas
    const canvas = new OffscreenCanvas(targetWidth, targetHeight);
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      throw new Error('Canvas context not available in worker');
    }

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
    
    // 4. Convert back to Blob/DataURL
    const outBlob = await canvas.convertToBlob({ type: 'image/png' });
    
    // Read as DataURL using standard FileReader asynchronously
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(outBlob);
    });

    self.postMessage({ type: 'success', dataUrl, aspectRatio: targetAspectRatio });

  } catch (error) {
    self.postMessage({ type: 'error', error: error instanceof Error ? error.message : 'Unknown error in worker' });
  }
};
