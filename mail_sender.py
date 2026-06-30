import os
import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
MAIL_TO = os.getenv("MAIL_TO")

resend.api_key = RESEND_API_KEY


def send_mail(subject, body):
    try:
        if not RESEND_API_KEY:
            return "RESEND_API_KEY が設定されていません"

        if not MAIL_TO:
            return "MAIL_TO が設定されていません"

        result = resend.Emails.send({
            "from": "Schedule App <onboarding@resend.dev>",
            "to": [MAIL_TO],
            "subject": subject,
            "html": f"<p>{body}</p>",
        })

        return "OK"

    except Exception as e:
        return f"メール送信エラー: {e}"