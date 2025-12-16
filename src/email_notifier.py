import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email_notification(subject, body, sender_email=None, sender_password=None, receiver_email=None):
    """
    Gmail을 통해 이메일 알림 전송
    
    Args:
        subject: 이메일 제목
        body: 이메일 본문
        sender_email: 발신자 이메일 (선택, 환경변수 GMAIL_USERNAME 사용)
        sender_password: Gmail 앱 비밀번호 (선택, 환경변수 GMAIL_PASSWORD 사용)
        receiver_email: 수신자 이메일 (선택, 환경변수 NOTIFICATION_EMAIL 사용)
    """
    try:
        # 환경변수에서 이메일 정보 가져오기
        sender_email = sender_email or os.getenv('GMAIL_USERNAME')
        sender_password = sender_password or os.getenv('GMAIL_PASSWORD')
        receiver_email = receiver_email or os.getenv('NOTIFICATION_EMAIL')
        
        # 필수 정보 확인
        if not all([sender_email, sender_password, receiver_email]):
            print("⚠️ 이메일 설정 정보 없음 (GMAIL_USERNAME, GMAIL_PASSWORD, NOTIFICATION_EMAIL)")
            return
        
        # 이메일 메시지 생성
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = receiver_email
        message['Subject'] = subject
        
        # 본문 추가
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Gmail SMTP 서버 연결
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        print(f"📧 이메일 전송 완료: {receiver_email}")
        
    except Exception as e:
        print(f"❌ 이메일 전송 실패: {e}")
