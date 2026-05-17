const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';

/**
 * Submit a processed (green-screen) Base64 image and its aspect ratio to the API.
 * Returns the server response JSON.
 */
export async function submitArtwork(
  imageData: string,
  aspectRatio: string,
  roomId: string,
): Promise<{ task_id: string; status: string }> {
  const res = await fetch(`${API_URL}/api/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_data: imageData, aspect_ratio: aspectRatio, room_id: roomId }),
  });

  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
