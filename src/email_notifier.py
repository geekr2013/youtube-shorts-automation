import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class EmailNotifier:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.username = os.getenv('SMTP_USERNAME')
        self.password = os.getenv('SMTP_PASSWORD')
        self.recipient = os.getenv('RECIPIENT_EMAIL')
        
        if not all([self.username, self.password, self.recipient]):
            print("⚠️ 이메일 설정이 완료되지 않았습니다.")
    
    def send_notification(self, subject, body):
        """
        이메일 알림 전송
        
        Args:
            subject: 이메일 제목
            body: 이메일 본문
        """
        try:
            # 이메일 메시지 생성
            message = MIMEMultipart()
            message['From'] = self.username
            message['To'] = self.recipient
            message['Subject'] = subject
            
            # 본문 추가
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            full_body = f"""
{body}

---
전송 시간: {timestamp}
자동화 시스템: AAGAG YouTube Shorts Automation
"""
            message.attach(MIMEText(full_body, 'plain', 'utf-8'))
            
            # SMTP 서버 연결 및 전송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(message)
            
            print(f"📧 이메일 전송 완료: {self.recipient}")
            
        except Exception as e:
            print(f"❌ 이메일 전송 실패: {str(e)}")
