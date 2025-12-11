import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

class EmailNotifier:
    def __init__(self):
        """이메일 발송기 초기화"""
        self.sender = os.environ.get('SENDER_EMAIL')
        self.password = os.environ.get('GMAIL_PASSWORD')
        self.receiver = os.environ.get('RECEIVER_EMAIL')
    
    def send_report(self, upload_results):
        """실행 결과 이메일 발송"""
        try:
            subject = f"[YouTube Shorts 자동화] {datetime.now().strftime('%Y-%m-%d')} 실행 결과"
            body = self.create_email_body(upload_results)
            
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = self.receiver
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            print("📧 이메일 발송 중...")
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            
            print("✅ 이메일 발송 완료")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 발송 실패: {e}")
            return False
    
    def create_email_body(self, results):
        """HTML 이메일 본문 생성"""
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #ff0000; color: white; padding: 20px; }}
                .summary {{ padding: 20px; background-color: #f0f0f0; margin: 10px 0; }}
                .video-item {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .success {{ color: green; }}
                .fail {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📺 YouTube Shorts 자동 업로드 결과</h1>
                <p>{datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}</p>
            </div>
            
            <div class="summary">
                <h2>📊 실행 요약</h2>
                <p><strong>총 업로드:</strong> {len(results)}개</p>
                <p class="success"><strong>성공:</strong> {success_count}개</p>
                <p class="fail"><strong>실패:</strong> {fail_count}개</p>
            </div>
            
            <h2>📝 상세 결과</h2>
        """
        
        for i, result in enumerate(results, 1):
            status = "✅ 성공" if result['success'] else "❌ 실패"
            status_class = "success" if result['success'] else "fail"
            
            html += f"""
            <div class="video-item">
                <p><strong>{i}. {result['title']}</strong></p>
                <p class="{status_class}">{status}</p>
            """
            
            if result['youtube_url']:
                html += f'<p>🔗 <a href="{result["youtube_url"]}">YouTube에서 보기</a></p>'
            
            html += "</div>"
        
        html += """
            <div style="padding: 20px; background-color: #f9f9f9; margin-top: 20px;">
                <p><em>✅ GitHub Actions로 자동 실행되었습니다.</em></p>
                <p><em>이 메일은 자동으로 발송되었습니다.</em></p>
            </div>
        </body>
        </html>
        """
        
        return html
