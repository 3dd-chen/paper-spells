import useSWR from 'swr';
import type { GalleryItem } from '../types';

const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';
const fetcher = (url: string) => fetch(url).then(r => r.json());
const poster = (url: string) => fetch(url, { method: 'POST' }).then(r => r.json());

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

  const videos = data?.filter(v => v.video_url) || [];
  return { videos, isLoaded: !!data || !!error, error };
}
