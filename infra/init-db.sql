-- Create the Langfuse database (if it doesn't exist)
-- Runs automatically on first PostgreSQL start via docker-entrypoint-initdb.d
SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
