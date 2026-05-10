import { useEffect, useRef, useCallback, useState } from 'react';

export interface GalleryItem {
  id: string;
  video_url: string | null;
  image_path: string | null;
  facing_direction?: string | null;
}

const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';
const POLL_INTERVAL = 10_000;

/**
 * Polls /api/gallery every POLL_INTERVAL ms.
 * Returns only items that have a video_url, de-duplicated by id.
 */
export function useGalleryPolling() {
  const [videos, setVideos] = useState<GalleryItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const seenIds = useRef<Set<string>>(new Set());

  const fetchAndUpdate = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/gallery`);
      if (!res.ok) return;
      const items: GalleryItem[] = await res.json();
      const newItems = items.filter(
        (item) => item.video_url && !seenIds.current.has(item.id),
      );
      if (newItems.length > 0) {
        newItems.forEach((i) => seenIds.current.add(i.id));
        setVideos((prev) => [...prev, ...newItems]);
      }
    } catch (err) {
      console.warn('Gallery fetch failed:', err);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    fetchAndUpdate();
    const id = setInterval(fetchAndUpdate, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [fetchAndUpdate]);

  return { videos, isLoaded };
}
