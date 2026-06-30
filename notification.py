import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import get_db, init_db
from mail_sender import send_mail

JST = ZoneInfo("Asia/Tokyo")

init_db()

def create_notifications(schedule_id, title, date, notify_day_before, notify_minutes_before, notify_at_time):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM notifications WHERE schedule_id = %s",
        (schedule_id,)
    )

    schedule_time = datetime.strptime(date, "%Y-%m-%dT%H:%M")

    if notify_day_before:
        day_before = schedule_time - timedelta(days=1)
        h, m = map(int, notify_day_before.split(":"))
        notify_time = day_before.replace(hour=h, minute=m)

        cur.execute(
            """
            INSERT INTO notifications (schedule_id, notify_time, message)
            VALUES (%s, %s, %s)
            """,
            (
                schedule_id,
                notify_time.strftime("%Y-%m-%dT%H:%M"),
                f"明日「{title}」があります。"
            )
        )

    if notify_minutes_before:
        minutes_list = notify_minutes_before.replace(" ", "").split(",")

        for minutes in minutes_list:
            if minutes.isdigit():
                minutes_int = int(minutes)
                notify_time = schedule_time - timedelta(minutes=minutes_int)

                cur.execute(
                    """
                    INSERT INTO notifications (schedule_id, notify_time, message)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        schedule_id,
                        notify_time.strftime("%Y-%m-%dT%H:%M"),
                        f"{minutes_int}分後に「{title}」があります。"
                    )
                )

    if notify_at_time == 1:
        cur.execute(
            """
            INSERT INTO notifications (schedule_id, notify_time, message)
            VALUES (%s, %s, %s)
            """,
            (
                schedule_id,
                schedule_time.strftime("%Y-%m-%dT%H:%M"),
                f"「{title}」の時間です。"
            )
        )

    conn.commit()
    cur.close()
    conn.close()


def notification_loop():
    while True:
        now = datetime.now(JST).strftime("%Y-%m-%dT%H:%M")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, message
            FROM notifications
            WHERE notify_time <= %s
            AND sent = FALSE
            """,
            (now,)
        )

        notifications = cur.fetchall()

        for notification in notifications:
            notification_id = notification[0]
            message = notification[1]

            result = send_mail("Schedule App 通知", message)

            if result == "OK":
                cur.execute(
                    "UPDATE notifications SET sent = TRUE WHERE id = %s",
                    (notification_id,)
                )

        conn.commit()
        cur.close()
        conn.close()

        time.sleep(30)


if __name__ == "__main__":
    notification_loop()