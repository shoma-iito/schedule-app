import os
import smtplib
from email.mime.text import MIMEText

MAIL_ADDRESS = os.getenv("MAIL_ADDRESS")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_TO = os.getenv("MAIL_TO")


def send_mail(subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = MAIL_ADDRESS
    msg["To"] = MAIL_TO

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(MAIL_ADDRESS, MAIL_PASSWORD)
            server.send_message(msg)

        return "OK"

    except Exception as e:
        return str(e)