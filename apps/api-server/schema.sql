CREATE TABLE IF NOT EXISTS artworks (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    image_path TEXT,
    helmet_image_path TEXT,
    video_url TEXT,
    status TEXT DEFAULT 'pending',
    provider_task_id TEXT,
    facing_direction TEXT,
    hidden INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- When the current generation attempt started (reset on regenerate).
    generating_started_at DATETIME
);

-- Existing databases need this before deploying code that writes it:
--   ALTER TABLE artworks ADD COLUMN generating_started_at DATETIME;
-- (see migrations/0001_add_generating_started_at.sql)

-- Migration for databases created before `hidden` existed.
-- SQLite has no "ADD COLUMN IF NOT EXISTS"; this is a no-op on a
-- correctly-provisioned DB and only needed for legacy ones.
-- Run manually if `hidden` is missing:
--   ALTER TABLE artworks ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS admins (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
