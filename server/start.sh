#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import time

import psycopg
from psycopg import sql

host = os.getenv("POSTGRES_HOST", "postgres")
port = int(os.getenv("POSTGRES_PORT", "5432"))
user = os.getenv("POSTGRES_USER", "postgres")
password = os.getenv("POSTGRES_PASSWORD", "postgres")
default_db = os.getenv("POSTGRES_DB", "postgres")
app_db = os.getenv("APP_DB_NAME", "mem0_app")
deadline = time.time() + 180

while True:
    try:
        with socket.create_connection((host, port), timeout=5):
            break
    except OSError:
        if time.time() > deadline:
            raise
        time.sleep(2)

while True:
    try:
        with psycopg.connect(
            host=host,
            port=port,
            dbname=default_db,
            user=user,
            password=password,
            autocommit=True,
        ) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (app_db,),
            ).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(app_db)))
            break
    except psycopg.OperationalError:
        if time.time() > deadline:
            raise
        time.sleep(2)
PY

alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port 8000
