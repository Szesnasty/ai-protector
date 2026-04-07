FROM pgvector/pgvector:pg16
COPY init-db.sql /docker-entrypoint-initdb.d/init-db.sql
