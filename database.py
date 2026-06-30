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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                notify_day_before TEXT,
                notify_minutes_before INTEGER,
                notify_at_time INTEGER DEFAULT 0
            )
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                notify_day_before TEXT,
                notify_minutes_before INTEGER,
                notify_at_time INTEGER DEFAULT 0
            )
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
    conn.close()