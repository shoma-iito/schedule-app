import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import get_db
from mail_sender import send_mail

JST = ZoneInfo("Asia/Tokyo")

def create_notifications(schedule_id, title, date, notify_day_before, notify_minutes_before, notify_at_time):
    conn = get_db()

    conn.execute(
        "DELETE FROM notifications WHERE schedule_id = ?",
        (schedule_id,)
    )

    schedule_time = datetime.strptime(date, "%Y-%m-%dT%H:%M")

    if notify_day_before:
        day_before = schedule_time - timedelta(days=1)
        h, m = map(int, notify_day_before.split(":"))
        notify_time = day_before.replace(hour=h, minute=m)

        conn.execute(
            "INSERT INTO notifications (schedule_id, notify_time, message) VALUES (?, ?, ?)",
            (schedule_id, notify_time.strftime("%Y-%m-%dT%H:%M"), f"明日「{title}」があります。")
        )

    if notify_minutes_before:
        minutes_list = notify_minutes_before.replace(" ", "").split(",")

        for minutes in minutes_list:
            if minutes.isdigit():
                minutes_int = int(minutes)
                notify_time = schedule_time - timedelta(minutes=minutes_int)

                conn.execute(
                    "INSERT INTO notifications (schedule_id, notify_time, message) VALUES (?, ?, ?)",
                    (
                        schedule_id,
                        notify_time.strftime("%Y-%m-%dT%H:%M"),
                        f"{minutes_int}分後に「{title}」があります。"
                    )
                )

    if notify_at_time == 1:
        conn.execute(
            "INSERT INTO notifications (schedule_id, notify_time, message) VALUES (?, ?, ?)",
            (schedule_id, schedule_time.strftime("%Y-%m-%dT%H:%M"), f"「{title}」の時間です。")
        )

    conn.commit()
    conn.close()

def notification_loop():
    while True:
        now = datetime.now(JST).strftime("%Y-%m-%dT%H:%M")

        conn = get_db()
        notifications = conn.execute(
            """
            SELECT id, message
            FROM notifications
            WHERE notify_time <= ?
            AND sent = 0
            """,
            (now,)
        ).fetchall()

        for notification in notifications:
            notification_id = notification[0]
            message = notification[1]

            send_mail("Schedule App 通知", message)

            conn.execute(
                "UPDATE notifications SET sent = 1 WHERE id = ?",
                (notification_id,)
            )

        conn.commit()
        conn.close()

        time.sleep(60)