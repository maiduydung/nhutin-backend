import smtplib
from email.mime.text import MIMEText
from config import SENDER_EMAIL, SENDER_EMAIL_APP_PASSWORD, EMAILS
from datetime import datetime
import traceback

def _send_email(subject, body, to_emails):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = ", ".join(to_emails)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_EMAIL_APP_PASSWORD)
            server.sendmail(msg["From"], to_emails, msg.as_string())
        print(f"📧 Email sent successfully: {subject}")
    except Exception as e:
        print(f"📧 Email failed to send: {subject} - {str(e)}")
        # Don't raise the exception to prevent function failure

def send_email(subject="Nhu Tin Bill of Materials", body="", to_emails=None):
    if to_emails is None:
        to_emails = EMAILS
    
    subject = f"{subject}"
    body = f"{body}"
    _send_email(subject=subject, body=body, to_emails=to_emails)
