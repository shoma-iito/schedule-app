from flask import Flask, render_template, request, redirect, session
import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import wraps
import os

from database import get_db, init_db
from notification import create_notifications
from mail_sender import send_mail

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

LOGIN_USERNAME = os.getenv("LOGIN_USERNAME")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD")

JST = ZoneInfo("Asia/Tokyo")

init_db()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return func(*args, **kwargs)
    return wrapper


def add_one_schedule(title, date, notify_day_before, notify_minutes_before, notify_at_time):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO schedules
        (title, date, notify_day_before, notify_minutes_before, notify_at_time)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (title, date, notify_day_before, notify_minutes_before, notify_at_time)
    )

    schedule_id = cur.fetchone()["id"]

    conn.commit()
    cur.close()
    conn.close()

    create_notifications(
        schedule_id,
        title,
        date,
        notify_day_before,
        notify_minutes_before,
        notify_at_time
    )


def create_repeating_schedules(
    title,
    first_date,
    repeat_type,
    repeat_weekday,
    repeat_month_day,
    repeat_end_date,
    notify_day_before,
    notify_minutes_before,
    notify_at_time
):
    start_dt = datetime.strptime(first_date, "%Y-%m-%dT%H:%M")

    if not repeat_end_date or repeat_type == "none":
        add_one_schedule(
            title,
            first_date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )
        return

    end_date = datetime.strptime(repeat_end_date, "%Y-%m-%d").date()

    if repeat_type == "daily":
        current = start_dt

        while current.date() <= end_date:
            add_one_schedule(
                title,
                current.strftime("%Y-%m-%dT%H:%M"),
                notify_day_before,
                notify_minutes_before,
                notify_at_time
            )
            current += timedelta(days=1)

    elif repeat_type == "weekly":
        target_weekday = int(repeat_weekday)
        current = start_dt

        while current.weekday() != target_weekday:
            current += timedelta(days=1)

        while current.date() <= end_date:
            add_one_schedule(
                title,
                current.strftime("%Y-%m-%dT%H:%M"),
                notify_day_before,
                notify_minutes_before,
                notify_at_time
            )
            current += timedelta(days=7)

    elif repeat_type == "monthly":
        target_day = int(repeat_month_day)
        year = start_dt.year
        month = start_dt.month

        while True:
            last_day = calendar.monthrange(year, month)[1]

            if target_day <= last_day:
                current = start_dt.replace(
                    year=year,
                    month=month,
                    day=target_day
                )

                if current >= start_dt and current.date() <= end_date:
                    add_one_schedule(
                        title,
                        current.strftime("%Y-%m-%dT%H:%M"),
                        notify_day_before,
                        notify_minutes_before,
                        notify_at_time
                    )

            month += 1

            if month == 13:
                month = 1
                year += 1

            if datetime(year, month, 1).date() > end_date:
                break


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        else:
            error = "IDまたはパスワードが違います。"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def home():
    today = datetime.now(JST)

    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    prev_year = year - 1 if month == 1 else year
    prev_month = 12 if month == 1 else month - 1

    next_year = year + 1 if month == 12 else year
    next_month = 1 if month == 12 else month + 1

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM schedules ORDER BY date")
    schedules = cur.fetchall()

    cur.close()
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
@login_required
def add():
    if request.method == "POST":
        title = request.form["title"]
        date = request.form["date"]
        notify_day_before = request.form.get("notify_day_before")
        notify_minutes_before = request.form.get("notify_minutes_before")
        notify_at_time = 1 if request.form.get("notify_at_time") else 0

        repeat_type = request.form.get("repeat_type", "none")
        repeat_weekday = request.form.get("repeat_weekday", "0")
        repeat_month_day = request.form.get("repeat_month_day", "1")
        repeat_end_date = request.form.get("repeat_end_date")

        if notify_minutes_before == "":
            notify_minutes_before = None

        create_repeating_schedules(
            title,
            date,
            repeat_type,
            repeat_weekday,
            repeat_month_day,
            repeat_end_date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )

        return redirect("/")

    return render_template("add.html")


@app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
@login_required
def edit(schedule_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        date = request.form["date"]
        notify_day_before = request.form.get("notify_day_before")
        notify_minutes_before = request.form.get("notify_minutes_before")
        notify_at_time = 1 if request.form.get("notify_at_time") else 0

        if notify_minutes_before == "":
            notify_minutes_before = None

        cur.execute(
            """
            UPDATE schedules
            SET title = %s,
                date = %s,
                notify_day_before = %s,
                notify_minutes_before = %s,
                notify_at_time = %s
            WHERE id = %s
            """,
            (
                title,
                date,
                notify_day_before,
                notify_minutes_before,
                notify_at_time,
                schedule_id
            )
        )

        conn.commit()
        cur.close()
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

    cur.execute(
        "SELECT * FROM schedules WHERE id = %s",
        (schedule_id,)
    )
    schedule = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("edit.html", schedule=schedule)


@app.route("/delete/<int:schedule_id>", methods=["POST"])
@login_required
def delete(schedule_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM notifications WHERE schedule_id = %s",
        (schedule_id,)
    )

    cur.execute(
        "DELETE FROM schedules WHERE id = %s",
        (schedule_id,)
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


@app.route("/test-mail")
@login_required
def test_mail():
    result = send_mail(
        "Schedule App テスト通知",
        "メール送信テストです。"
    )

    return str(result)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)