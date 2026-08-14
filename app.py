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


# =========================================
# ログイン確認
# =========================================

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")

        return func(*args, **kwargs)

    return wrapper


# =========================================
# 予定を1件追加
# =========================================

def add_one_schedule(
    title,
    date,
    end_date,
    notify_day_before,
    notify_minutes_before,
    notify_at_time
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO schedules
        (
            title,
            date,
            end_date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            title,
            date,
            end_date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )
    )

    row = cur.fetchone()

    try:
        schedule_id = row["id"]
    except (TypeError, KeyError):
        schedule_id = row[0]

    conn.commit()
    cur.close()
    conn.close()

    # 通知は開始日時を基準にする
    create_notifications(
        schedule_id,
        title,
        date,
        notify_day_before,
        notify_minutes_before,
        notify_at_time
    )


# =========================================
# 繰り返し予定
# =========================================

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
    start_dt = datetime.strptime(
        first_date,
        "%Y-%m-%dT%H:%M"
    )

    end_date = datetime.strptime(
        repeat_end_date,
        "%Y-%m-%d"
    ).date()

    # 毎日
    if repeat_type == "daily":
        current = start_dt

        while current.date() <= end_date:
            add_one_schedule(
                title,
                current.strftime("%Y-%m-%dT%H:%M"),
                None,
                notify_day_before,
                notify_minutes_before,
                notify_at_time
            )

            current += timedelta(days=1)

    # 毎週
    elif repeat_type == "weekly":
        target_weekday = int(repeat_weekday)
        current = start_dt

        # 指定曜日まで進める
        while current.weekday() != target_weekday:
            current += timedelta(days=1)

        # 終了日まで毎週追加
        while current.date() <= end_date:
            add_one_schedule(
                title,
                current.strftime("%Y-%m-%dT%H:%M"),
                None,
                notify_day_before,
                notify_minutes_before,
                notify_at_time
            )

            current += timedelta(days=7)

    # 毎月
    elif repeat_type == "monthly":
        target_day = int(repeat_month_day)

        year = start_dt.year
        month = start_dt.month

        while True:
            last_day = calendar.monthrange(
                year,
                month
            )[1]

            if target_day <= last_day:
                current = start_dt.replace(
                    year=year,
                    month=month,
                    day=target_day
                )

                if (
                    current >= start_dt
                    and current.date() <= end_date
                ):
                    add_one_schedule(
                        title,
                        current.strftime("%Y-%m-%dT%H:%M"),
                        None,
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


# =========================================
# ログイン
# =========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if (
            username == LOGIN_USERNAME
            and password == LOGIN_PASSWORD
        ):
            session["logged_in"] = True
            return redirect("/")

        error = "IDまたはパスワードが違います。"

    return render_template(
        "login.html",
        error=error
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================================
# カレンダー
# =========================================

@app.route("/")
@login_required
def home():
    today = datetime.now(JST)

    year = request.args.get(
        "year",
        today.year,
        type=int
    )

    month = request.args.get(
        "month",
        today.month,
        type=int
    )

    prev_year = year - 1 if month == 1 else year
    prev_month = 12 if month == 1 else month - 1

    next_year = year + 1 if month == 12 else year
    next_month = 1 if month == 12 else month + 1

    cal = calendar.Calendar(firstweekday=6)

    month_days = cal.monthdayscalendar(
        year,
        month
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM schedules
        ORDER BY date
        """
    )

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


# =========================================
# 通常予定追加
# =========================================

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        title = request.form["title"]

        # 開始日時
        date = request.form["date"]

        # 終了日時
        end_date = request.form.get("end_date")

        if end_date == "":
            end_date = None

        # 終了日時がある場合は前後関係を確認
        if end_date:
            start_dt = datetime.strptime(
                date,
                "%Y-%m-%dT%H:%M"
            )

            finish_dt = datetime.strptime(
                end_date,
                "%Y-%m-%dT%H:%M"
            )

            if finish_dt < start_dt:
                return (
                    "終了日時は開始日時より後にしてください。",
                    400
                )

        notify_day_before = request.form.get(
            "notify_day_before"
        )

        notify_minutes_before = request.form.get(
            "notify_minutes_before"
        )

        notify_at_time = (
            1
            if request.form.get("notify_at_time")
            else 0
        )

        if notify_minutes_before == "":
            notify_minutes_before = None

        add_one_schedule(
            title,
            date,
            end_date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )

        return redirect("/")

    return render_template("add.html")


# =========================================
# 繰り返し予定
# =========================================

@app.route("/repeat", methods=["GET", "POST"])
@login_required
def repeat():
    if request.method == "POST":
        title = request.form["title"]

        start_date = request.form["start_date"]
        time_value = request.form["time"]

        repeat_type = request.form["repeat_type"]

        repeat_weekday = request.form.get(
            "repeat_weekday",
            "0"
        )

        repeat_month_day = request.form.get(
            "repeat_month_day",
            "1"
        )

        repeat_end_date = request.form[
            "repeat_end_date"
        ]

        notify_day_before = request.form.get(
            "notify_day_before"
        )

        notify_minutes_before = request.form.get(
            "notify_minutes_before"
        )

        notify_at_time = (
            1
            if request.form.get("notify_at_time")
            else 0
        )

        if notify_minutes_before == "":
            notify_minutes_before = None

        first_date = (
            f"{start_date}T{time_value}"
        )

        create_repeating_schedules(
            title,
            first_date,
            repeat_type,
            repeat_weekday,
            repeat_month_day,
            repeat_end_date,
            notify_day_before,
            notify_minutes_before,
            notify_at_time
        )

        return redirect("/")

    return render_template("repeat.html")


# =========================================
# 編集
# =========================================

@app.route(
    "/edit/<int:schedule_id>",
    methods=["GET", "POST"]
)
@login_required
def edit(schedule_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]

        date = request.form["date"]

        end_date = request.form.get("end_date")

        if end_date == "":
            end_date = None

        if end_date:
            start_dt = datetime.strptime(
                date,
                "%Y-%m-%dT%H:%M"
            )

            finish_dt = datetime.strptime(
                end_date,
                "%Y-%m-%dT%H:%M"
            )

            if finish_dt < start_dt:
                cur.close()
                conn.close()

                return (
                    "終了日時は開始日時より後にしてください。",
                    400
                )

        notify_day_before = request.form.get(
            "notify_day_before"
        )

        notify_minutes_before = request.form.get(
            "notify_minutes_before"
        )

        notify_at_time = (
            1
            if request.form.get("notify_at_time")
            else 0
        )

        if notify_minutes_before == "":
            notify_minutes_before = None

        cur.execute(
            """
            UPDATE schedules
            SET
                title = %s,
                date = %s,
                end_date = %s,
                notify_day_before = %s,
                notify_minutes_before = %s,
                notify_at_time = %s
            WHERE id = %s
            """,
            (
                title,
                date,
                end_date,
                notify_day_before,
                notify_minutes_before,
                notify_at_time,
                schedule_id
            )
        )

        conn.commit()
        cur.close()
        conn.close()

        # 通知を作り直す
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
        """
        SELECT *
        FROM schedules
        WHERE id = %s
        """,
        (schedule_id,)
    )

    schedule = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "edit.html",
        schedule=schedule
    )


# =========================================
# 削除
# =========================================

@app.route(
    "/delete/<int:schedule_id>",
    methods=["POST"]
)
@login_required
def delete(schedule_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM notifications
        WHERE schedule_id = %s
        """,
        (schedule_id,)
    )

    cur.execute(
        """
        DELETE FROM schedules
        WHERE id = %s
        """,
        (schedule_id,)
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


# =========================================
# メールテスト
# =========================================

@app.route("/test-mail")
@login_required
def test_mail():
    result = send_mail(
        "Schedule App テスト通知",
        "メール送信テストです。"
    )

    return str(result)


if __name__ == "__main__":
    app.run(
        debug=True,
        use_reloader=False
    )