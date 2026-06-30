from flask import Flask, render_template, request, redirect
import calendar
import threading
from datetime import datetime

from database import get_db, init_db
from notification import create_notifications, notification_loop
from mail_sender import send_mail

app = Flask(__name__)

init_db()

thread = threading.Thread(target=notification_loop, daemon=True)
thread.start()

@app.route("/")
def home():
    today = datetime.today()

    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    prev_year = year - 1 if month == 1 else year
    prev_month = 12 if month == 1 else month - 1

    next_year = year + 1 if month == 12 else year
    next_month = 1 if month == 12 else month + 1

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)

    conn = get_db()
    schedules = conn.execute(
        "SELECT * FROM schedules ORDER BY date"
    ).fetchall()
    conn.close()

    return render_template(
        "index.html",
        year=year,
        month=month,
        month_days=month_days,
        schedules=schedules,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        today_year=today.year,
        today_month=today.month,
        today_day=today.day
    )

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        title = request.form["title"]
        date = request.form["date"]
        notify_day_before = request.form.get("notify_day_before")
        notify_minutes_before = request.form.get("notify_minutes_before")
        notify_at_time = 1 if request.form.get("notify_at_time") else 0

        if notify_minutes_before == "":
            notify_minutes_before = None

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO schedules
            (title, date, notify_day_before, notify_minutes_before, notify_at_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, date, notify_day_before, notify_minutes_before, notify_at_time)
        )

        schedule_id = cur.lastrowid

        conn.commit()
        conn.close()

        create_notifications(
            schedule_id,
            title,
            date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )

        return redirect("/")

    return render_template("add.html")

@app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
def edit(schedule_id):
    conn = get_db()

    if request.method == "POST":
        title = request.form["title"]
        date = request.form["date"]
        notify_day_before = request.form.get("notify_day_before")
        notify_minutes_before = request.form.get("notify_minutes_before")
        notify_at_time = 1 if request.form.get("notify_at_time") else 0

        if notify_minutes_before == "":
            notify_minutes_before = None

        conn.execute(
            """
            UPDATE schedules
            SET title = ?, date = ?, notify_day_before = ?,
                notify_minutes_before = ?, notify_at_time = ?
            WHERE id = ?
            """,
            (title, date, notify_day_before, notify_minutes_before, notify_at_time, schedule_id)
        )

        conn.commit()
        conn.close()

        create_notifications(
            schedule_id,
            title,
            date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )

        return redirect("/")

    schedule = conn.execute(
        "SELECT * FROM schedules WHERE id = ?",
        (schedule_id,)
    ).fetchone()

    conn.close()

    return render_template("edit.html", schedule=schedule)

@app.route("/delete/<int:schedule_id>", methods=["POST"])
def delete(schedule_id):
    conn = get_db()

    conn.execute(
        "DELETE FROM notifications WHERE schedule_id = ?",
        (schedule_id,)
    )

    conn.execute(
        "DELETE FROM schedules WHERE id = ?",
        (schedule_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/test-mail")
def test_mail():
    try:
        send_mail(
            "Schedule App テスト通知",
            "メール送信テストです。Schedule App から送信されています。"
        )
        return "メールを送信しました。"
    except Exception as e:
        return f"エラー内容: {e}"


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)