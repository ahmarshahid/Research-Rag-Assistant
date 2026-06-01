-- PostgreSQL initialization script
-- Runs once when the database container is first created.
-- Tables are created by SQLAlchemy (Base.metadata.create_all) on app startup,
-- so we only need extensions here.

-- UUID support (used by SQLAlchemy UUID primary keys via server_default)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Full-text search support (optional, useful for future text search features)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
