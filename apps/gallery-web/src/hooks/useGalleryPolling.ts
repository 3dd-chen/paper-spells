import useSWR from 'swr';
import type { GalleryItem } from '../types';

const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';
// Throw on non-2xx so SWR keeps the last good data and exposes `error`,
// instead of storing an error body like {"detail": ...} as `data`.
async function parseOrThrow(r: Response) {
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
const fetcher = (url: string) => fetch(url).then(parseOrThrow);
const poster = (url: string) => fetch(url, { method: 'POST' }).then(parseOrThrow);

export function useGalleryPolling() {
  const roomId = new URLSearchParams(window.location.search).get('room') || 'default';

  // Fast gallery refresh — DB-only read, no external calls.
  const { data, error } = useSWR<GalleryItem[]>(`${API_URL}/api/gallery?room_id=${roomId}`, fetcher, {
    refreshInterval: 5000,
    revalidateOnFocus: false,
  });

  // Slower poll — triggers Veo check_status and updates DB.
  // Runs independently so it doesn't block gallery rendering.
  useSWR(`${API_URL}/api/poll?room_id=${roomId}`, poster, {
    refreshInterval: 15000,
    revalidateOnFocus: false,
  });

  const videos = Array.isArray(data) ? data.filter(v => v.video_url) : [];
  return { videos, isLoaded: !!data || !!error, error };
}
