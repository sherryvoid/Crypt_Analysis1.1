# services/email_sender.py

import smtplib
from email.message import EmailMessage
import os
import logging
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# Load local .env values for email sending without requiring shell exports.
load_dotenv()

SENDER_EMAIL_ENV_VAR = "EMAIL_SENDER"
DEFAULT_EMAIL_ENV_VAR = "DEFAULT_EMAIL"
APP_PASSWORD_ENV_VAR = "EMAIL_APP_PASSWORD"
SENDER_EMAIL = os.getenv(SENDER_EMAIL_ENV_VAR, "")
DEFAULT_EMAIL = os.getenv(DEFAULT_EMAIL_ENV_VAR, SENDER_EMAIL)


def _get_sender_email() -> str:
    sender_email = os.getenv(SENDER_EMAIL_ENV_VAR) or SENDER_EMAIL
    if not sender_email:
        raise RuntimeError(
            f"{SENDER_EMAIL_ENV_VAR} is not set. Add it to your environment or .env before sending email."
        )
    return sender_email


def _get_app_password() -> str:
    app_password = os.getenv(APP_PASSWORD_ENV_VAR)
    if not app_password:
        raise RuntimeError(
            f"{APP_PASSWORD_ENV_VAR} is not set. Add it to your environment or .env before sending email."
        )
    return app_password


def send_email_report(to_email: str, pdf_path: str):
    sender_email = _get_sender_email()
    log.info(f"Preparing email report send from {sender_email} to {to_email}")
    msg = EmailMessage()
    msg['Subject'] = "Your Crypto Analysis Report"
    msg['From'] = sender_email
    msg['To'] = to_email
    msg.set_content(
        "Hello,\n\nPlease find attached your crypto analysis PDF report.\n\nBest regards.")

    with open(pdf_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(pdf_path)

    msg.add_attachment(file_data, maintype='application',
                       subtype='pdf', filename=file_name)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(sender_email, _get_app_password())
        smtp.send_message(msg)

    log.info(f"Email sent to {to_email} with attachment {file_name}")
    print(f"✅ Email sent to {to_email} with attachment {file_name}")
