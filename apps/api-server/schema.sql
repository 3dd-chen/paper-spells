CREATE TABLE IF NOT EXISTS artworks (
    id TEXT PRIMARY KEY,
    image_path TEXT,
    video_url TEXT,
    status TEXT DEFAULT 'pending',
    provider_task_id TEXT,
    facing_direction TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
