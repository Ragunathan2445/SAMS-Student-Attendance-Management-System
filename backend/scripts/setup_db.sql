-- Run once as the PostgreSQL superuser, e.g.:
--   psql -U postgres -f scripts/setup_db.sql
-- Creates the application role, the demo database and (optionally) a separate test database.

CREATE ROLE sams_user WITH LOGIN PASSWORD 'sams_password';
CREATE DATABASE sams_db OWNER sams_user ENCODING 'UTF8';
CREATE DATABASE sams_test OWNER sams_user ENCODING 'UTF8';   -- used only by the integration tests
