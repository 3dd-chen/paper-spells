/**
 * Resolves a raw video URL from the DB into a fully qualified HTTPS URL.
 * Handles the case where R2_PUBLIC_URL was stored without a scheme.
 */
const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE_URL as string;

export function resolveVideoUrl(raw: string): string {
  if (!raw) return '';

  // If the URL contains our media domain (possibly stored without scheme),
  // rewrite to a proper https:// URL starting at the /videos path.
  // ONLY do this in development to use Vite proxy. In production, use the absolute URL.
  if (import.meta.env.DEV && MEDIA_BASE && raw.includes(MEDIA_BASE)) {
    const idx = raw.indexOf('/videos');
    if (idx !== -1) {
      // Return relative path to use Vite proxy (/videos/...)
      return raw.substring(idx);
    }
  }

  if (!raw.startsWith('http')) return `https://${raw}`;
  return raw;
}
