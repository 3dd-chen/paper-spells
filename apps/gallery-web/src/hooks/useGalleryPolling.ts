import useSWR from 'swr';
import type { GalleryItem } from '../types';

const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';
const fetcher = (url: string) => fetch(url).then(r => r.json());

export function useGalleryPolling() {
  const { data, error } = useSWR<GalleryItem[]>(`${API_URL}/api/gallery`, fetcher, {
    refreshInterval: 10000,
  });

  const videos = data?.filter(v => v.video_url) || [];
  return { videos, isLoaded: !!data || !!error };
}
