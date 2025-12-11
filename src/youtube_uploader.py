import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

class YouTubeUploader:
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self):
        """YouTube API 초기화"""
        self.youtube = self.get_authenticated_service()
    
    def get_authenticated_service(self):
        """YouTube API 인증"""
        credentials = None
        
        # GitHub Actions 환경에서는 환경 변수에서 토큰 로드
        client_secret_json = os.environ.get('YOUTUBE_CLIENT_SECRET')
        refresh_token = os.environ.get('YOUTUBE_REFRESH_TOKEN')
        
        if client_secret_json and refresh_token:
            # 환경 변수에서 인증 정보 로드
            client_config = json.loads(client_secret_json)
            
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=client_config['installed']['token_uri'],
                client_id=client_config['installed']['client_id'],
                client_secret=client_config['installed']['client_secret'],
                scopes=self.SCOPES
            )
            
            # 토큰 갱신
            if credentials.expired:
                credentials.refresh(Request())
        
        return build('youtube', 'v3', credentials=credentials)
    
    def upload_video(self, filepath, title, description=""):
        """YouTube Shorts 업로드"""
        try:
            print(f"📤 YouTube 업로드 중: {title[:50]}...")
            
            # Shorts용 제목 (최대 100자)
            shorts_title = title[:95] + " #Shorts" if len(title) > 95 else title + " #Shorts"
            
            # 업로드 메타데이터
            body = {
                'snippet': {
                    'title': shorts_title,
                    'description': description,
                    'tags': ['Shorts', '재미', '힐링', '웃긴영상'],
                    'categoryId': '23'  # Comedy
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # 동영상 파일 업로드
            media = MediaFileUpload(filepath, chunksize=-1, resumable=True)
            
            request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = request.execute()
            
            video_id = response['id']
            video_url = f"https://youtube.com/shorts/{video_id}"
            
            print(f"✅ 업로드 완료: {video_url}")
            return video_url
            
        except Exception as e:
            print(f"❌ 업로드 실패: {str(e)}")
            return None
    
    def upload_multiple_videos(self, processed_videos):
        """여러 동영상 일괄 업로드"""
        results = []
        
        for i, video_info in enumerate(processed_videos, 1):
            print(f"\n[{i}/{len(processed_videos)}]")
            
            url = self.upload_video(
                filepath=video_info['filepath'],
                title=video_info['korean_title'],
                description=video_info['description']
            )
            
            results.append({
                'title': video_info['korean_title'],
                'youtube_url': url,
                'success': url is not None
            })
        
        return results
