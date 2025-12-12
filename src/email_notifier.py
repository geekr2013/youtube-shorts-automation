import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

class EmailNotifier:
    """Gmail을 통한 이메일 알림"""
    
    def __init__(self, sender_email, password):
        """
        이메일 알림 초기화
        
        Args:
            sender_email: 발신자 Gmail 주소
            password: Gmail 앱 비밀번호
        """
        self.sender_email = sender_email
        self.password = password
    
    def send_notification(self, subject, message, video_data=None):
        """
        이메일 알림 전송
        
        Args:
            subject: 이메일 제목
            message: 이메일 본문
            video_data: 업로드된 영상 정보 리스트
        """
        receiver_email = os.getenv('RECEIVER_EMAIL')
        
        if not receiver_email:
            print("❌ RECEIVER_EMAIL 환경변수가 설정되지 않았습니다.")
            return
        
        # HTML 이메일 작성
        html_content = self._create_html_email(subject, message, video_data)
        
        # 이메일 메시지 생성
        msg = MIMEMultipart('alternative')
        msg['From'] = self.sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        # HTML 본문 추가
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        try:
            # Gmail SMTP 서버 연결
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender_email, self.password)
                server.send_message(msg)
                print(f"✅ 이메일 전송 완료: {receiver_email}")
                
        except Exception as e:
            print(f"❌ 이메일 전송 실패: {e}")
    
    def _create_html_email(self, subject, message, video_data):
        """
        HTML 형식의 이메일 본문 생성
        
        Args:
            subject: 이메일 제목
            message: 기본 메시지
            video_data: 영상 정보 리스트
        
        Returns:
            str: HTML 형식의 이메일 본문
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Malgun Gothic', Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    padding: 30px;
                }}
                .video-item {{
                    background-color: #f9f9f9;
                    border-left: 4px solid #667eea;
                    padding: 15px;
                    margin-bottom: 15px;
                    border-radius: 5px;
                }}
                .video-item h3 {{
                    margin: 0 0 10px 0;
                    color: #333;
                }}
                .video-link {{
                    display: inline-block;
                    background-color: #667eea;
                    color: white;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 10px;
                }}
                .video-link:hover {{
                    background-color: #764ba2;
                }}
                .success {{
                    color: #28a745;
                    font-weight: bold;
                }}
                .failed {{
                    color: #dc3545;
                    font-weight: bold;
                }}
                .footer {{
                    background-color: #f5f5f5;
                    padding: 20px;
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                }}
                .keyword {{
                    display: inline-block;
                    background-color: #e3f2fd;
                    color: #1976d2;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-size: 12px;
                    margin-top: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎬 {subject}</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">{current_time}</p>
                </div>
                <div class="content">
                    <p style="font-size: 16px; color: #555;">{message}</p>
        """
        
        if video_data:
            success_count = sum(1 for v in video_data if v.get('status') == 'success')
            failed_count = len(video_data) - success_count
            
            html += f"""
                    <div style="margin: 20px 0; padding: 15px; background-color: #e8f5e9; border-radius: 5px;">
                        <p style="margin: 0;">
                            <span class="success">✅ 성공: {success_count}개</span>
                            {f'<span class="failed" style="margin-left: 20px;">❌ 실패: {failed_count}개</span>' if failed_count > 0 else ''}
                        </p>
                    </div>
            """
            
            for i, video in enumerate(video_data, 1):
                status = video.get('status', 'unknown')
                title = video.get('title', '제목 없음')
                keyword = video.get('keyword', '')
                
                if status == 'success':
                    video_url = video.get('url', '#')
                    html += f"""
                    <div class="video-item">
                        <h3>{i}. {title}</h3>
                        {f'<span class="keyword">🔑 {keyword}</span>' if keyword else ''}
                        <br>
                        <a href="{video_url}" class="video-link" target="_blank">
                            🎥 YouTube에서 보기
                        </a>
                    </div>
                    """
                else:
                    html += f"""
                    <div class="video-item" style="border-left-color: #dc3545;">
                        <h3>{i}. {title}</h3>
                        {f'<span class="keyword">🔑 {keyword}</span>' if keyword else ''}
                        <p class="failed">❌ 업로드 실패</p>
                    </div>
                    """
        
        html += """
                </div>
                <div class="footer">
                    <p>이 이메일은 GitHub Actions에서 자동으로 발송되었습니다.</p>
                    <p>YouTube Shorts 자동 업로드 시스템 🤖</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
