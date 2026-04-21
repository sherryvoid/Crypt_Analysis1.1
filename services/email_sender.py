# services/email_sender.py

import smtplib
from email.message import EmailMessage
import os

# IMPORTANT: Replace with your actual Gmail address and App Password securely (see instructions)
SENDER_EMAIL = "shaheryarbutt007@gmail.com"
APP_PASSWORD = "gliwsluhskzknzgf"  # <-- Replace with your Gmail App Password


def send_email_report(to_email: str, pdf_path: str):
    msg = EmailMessage()
    msg['Subject'] = "Your Crypto Analysis Report"
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg.set_content(
        "Hello,\n\nPlease find attached your crypto analysis PDF report.\n\nBest regards.")

    with open(pdf_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(pdf_path)

    msg.add_attachment(file_data, maintype='application',
                       subtype='pdf', filename=file_name)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)

    print(f"✅ Email sent to {to_email} with attachment {file_name}")
# sherry
