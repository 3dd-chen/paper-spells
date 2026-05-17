const API_URL = import.meta.env.VITE_API_BASE_URL as string ?? '';

const TOKEN_KEY = 'admin_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isTokenValid(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp > Date.now() / 1000;
  } catch {
    return false;
  }
}

async function adminFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  return fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
}

export async function login(username: string, password: string): Promise<{ token: string; expires_at: number }> {
  const res = await fetch(`${API_URL}/api/admin/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error('Invalid credentials');
  return res.json();
}

export async function logout(): Promise<void> {
  await adminFetch('/api/admin/logout', { method: 'POST' });
  clearToken();
}

export async function getRooms(): Promise<{ room_id: string; count: number }[]> {
  const res = await adminFetch('/api/admin/rooms');
  if (!res.ok) throw new Error('Unauthorized');
  return res.json();
}

export async function getRoomArtworks(roomId: string): Promise<AdminArtwork[]> {
  const res = await adminFetch(`/api/admin/rooms/${encodeURIComponent(roomId)}`);
  if (!res.ok) throw new Error('Unauthorized');
  return res.json();
}

export async function hideArtwork(id: string): Promise<void> {
  await adminFetch(`/api/admin/artworks/${id}/hide`, { method: 'PATCH' });
}

export async function unhideArtwork(id: string): Promise<void> {
  await adminFetch(`/api/admin/artworks/${id}/unhide`, { method: 'PATCH' });
}

export async function deleteArtwork(id: string): Promise<void> {
  const res = await adminFetch(`/api/admin/artworks/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Delete failed');
}

export interface AdminArtwork {
  id: string;
  room_id: string;
  status: string;
  hidden: number;
  video_url?: string;
  image_path?: string;
  facing_direction?: string;
  created_at?: string;
}
