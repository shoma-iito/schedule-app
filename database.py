import os
import sqlite3
import psycopg2
import psycopg2.extras

DB_NAME = "schedule.db"
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    if DATABASE_URL:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.DictCursor
        )

    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    if DATABASE_URL:
        # schedules テーブル
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                end_date TEXT,
                notify_day_before TEXT,
                notify_minutes_before TEXT,
                notify_at_time INTEGER DEFAULT 0
            )
        """)

        # 既存テーブルに end_date が無い場合だけ追加
        cur.execute("""
            ALTER TABLE schedules
            ADD COLUMN IF NOT EXISTS end_date TEXT
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                schedule_id INTEGER NOT NULL,
                notify_time TEXT NOT NULL,
                message TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                FOREIGN KEY(schedule_id) REFERENCES schedules(id)
            )
        """)

    else:
        # SQLite
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                end_date TEXT,
                notify_day_before TEXT,
                notify_minutes_before TEXT,
                notify_at_time INTEGER DEFAULT 0
            )
        """)

        # SQLiteは ADD COLUMN IF NOT EXISTS が使えないので確認
        cur.execute("PRAGMA table_info(schedules)")
        columns = [row[1] for row in cur.fetchall()]

        if "end_date" not in columns:
            cur.execute("""
                ALTER TABLE schedules
                ADD COLUMN end_date TEXT
            """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                notify_time TEXT NOT NULL,
                message TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                FOREIGN KEY(schedule_id) REFERENCES schedules(id)
            )
        """)

    conn.commit()
    cur.close()
    conn.close()