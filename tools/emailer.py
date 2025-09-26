import os, smtplib
from email.message import EmailMessage

def send_certificate(recipient, subject, body, attachment_path):
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    sender = os.getenv('EMAIL_FROM', smtp_user)
    if not smtp_server or not smtp_user or not smtp_pass:
        raise RuntimeError('SMTP not configured via env variables')
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.set_content(body)
    with open(attachment_path, 'rb') as f:
        data = f.read()
    msg.add_attachment(data, maintype='application', subtype='pdf', filename=os.path.basename(attachment_path))
    with smtplib.SMTP(smtp_server, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)
