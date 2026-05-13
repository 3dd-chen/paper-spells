import useSWR from 'swr';
import type { GalleryItem } from '../types';

const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';
const fetcher = (url: string) => fetch(url).then(r => r.json());

export function useGalleryPolling() {
  const { data, error } = useSWR<GalleryItem[]>(`${API_URL}/api/gallery`, fetcher, {
    refreshInterval: 20000, // 每 20 秒輪詢一次
    revalidateOnFocus: false, // 畫面是靜態展示，不需要在視窗切換時頻繁觸發更新
  });

  const videos = data?.filter(v => v.video_url) || [];
  return { videos, isLoaded: !!data || !!error };
}
