import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email_notification(subject, body, sender_email, sender_password, receiver_email):
    """
    Gmail을 통해 이메일 알림 전송
    
    Args:
        subject: 이메일 제목
        body: 이메일 본문
        sender_email: 발신자 이메일
        sender_password: Gmail 앱 비밀번호
        receiver_email: 수신자 이메일
    """
    try:
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
