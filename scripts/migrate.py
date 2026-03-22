#!/usr/bin/env python3
"""Simple SQL migration runner.

Tracks applied migrations in a schema_migrations table.
Runs all pending .sql files from migrations/ in alphabetical order.

Usage:
    python scripts/migrate.py          # Apply pending migrations
    python scripts/migrate.py status   # Show migration status
"""

import sys
from pathlib import Path

import psycopg
from _db import DATABASE_URL

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main():
    show_status = len(sys.argv) > 1 and sys.argv[1] == "status"

    conn = psycopg.connect(DATABASE_URL)

    # Ensure tracking table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(50) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()

    # Get already-applied versions
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}

    # Find all migration files
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print("No migration files found in migrations/")
        conn.close()
        return

    if show_status:
        print("Migration status:")
        for f in sql_files:
            status = "applied" if f.stem in applied else "PENDING"
            print(f"  {f.name:<40} {status}")
        conn.close()
        return

    # Run pending migrations
    pending = [f for f in sql_files if f.stem not in applied]

    if not pending:
        print("All migrations already applied.")
        conn.close()
        return

    for migration_file in pending:
        version = migration_file.stem
        print(f"Applying {migration_file.name}...", end=" ", flush=True)

        sql = migration_file.read_text(encoding="utf-8")
        try:
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            conn.commit()
            print("OK")
        except Exception as e:
            conn.rollback()
            print(f"FAILED: {e}")
            conn.close()
            sys.exit(1)

    conn.close()

    # Verify
    with psycopg.connect(DATABASE_URL) as verify:
        tables = verify.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ).fetchall()
        print(f"\nTables: {[t[0] for t in tables]}")


if __name__ == "__main__":
    main()
