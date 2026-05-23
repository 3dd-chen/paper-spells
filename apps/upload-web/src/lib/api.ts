const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';

export async function analyzeDirection(imageData: string): Promise<{ direction: string; description?: string }> {
  const res = await fetch(`${API_URL}/api/analyze-direction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_data: imageData }),
  });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

/**
 * Submit a processed (green-screen) Base64 image and its aspect ratio to the API.
 * Returns the server response JSON.
 */
export async function submitArtwork(
  imageData: string,
  aspectRatio: string,
  roomId: string,
  originalDirection: string,
  characterDescription?: string,
): Promise<{ task_id: string; status: string }> {
  const res = await fetch(`${API_URL}/api/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_data: imageData,
      aspect_ratio: aspectRatio,
      room_id: roomId,
      original_direction: originalDirection,
      character_description: characterDescription,
    }),
  });

  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
