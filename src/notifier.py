"""선택 사항인 Gmail 운영 알림."""

import logging
import os
import smtplib
from email.mime.text import MIMEText

LOGGER = logging.getLogger(__name__)


def send_notification(subject: str, body: str) -> bool:
    sender = os.getenv("SENDER_EMAIL", "")
    password = os.getenv("GMAIL_PASSWORD", "")
    receiver = os.getenv("RECEIVER_EMAIL", "")
    if not all([sender, password, receiver]):
        LOGGER.info("이메일 알림 설정이 없어 건너뜁니다.")
        return False
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = receiver
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(sender, password)
            server.send_message(message)
        return True
    except Exception as exc:
        LOGGER.warning("이메일 알림 전송 실패: %s", exc)
        return False

