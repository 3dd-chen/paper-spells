-- Track when the current generation attempt started, so regenerated artworks
-- aren't marked failed by cleanup_stuck_artworks based on their created_at.
-- Run once on the remote DB BEFORE deploying the code that writes this column:
--   wrangler d1 execute paper-spells-db --remote --file migrations/0001_add_generating_started_at.sql
ALTER TABLE artworks ADD COLUMN generating_started_at DATETIME;
