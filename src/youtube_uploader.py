import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle

class YouTubeUploader:
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self):
        self.credentials = None
        self.youtube = None
        self._authenticate()
    
    def _authenticate(self):
        """YouTube API 인증"""
        token_file = Path('data/youtube_token.pickle')
        
        # 저장된 토큰 로드
        if token_file.exists():
            with open(token_file, 'rb') as token:
                self.credentials = pickle.load(token)
        
        # 토큰이 없거나 만료된 경우 갱신
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                # GitHub Secrets에서 OAuth 클라이언트 정보 가져오기
                # YOUTUBE_CLIENT_ID가 없으면 CLIENT_SECRET에서 추출 시도
                client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
                refresh_token = os.getenv('YOUTUBE_REFRESH_TOKEN')
                
                # CLIENT_SECRET이 JSON 형식인 경우 파싱
                if client_secret and client_secret.startswith('{'):
                    import json
                    try:
                        secret_data = json.loads(client_secret)
                        if 'installed' in secret_data:
                            client_id = secret_data['installed']['client_id']
                            client_secret_value = secret_data['installed']['client_secret']
                        elif 'web' in secret_data:
                            client_id = secret_data['web']['client_id']
                            client_secret_value = secret_data['web']['client_secret']
                        else:
                            print("❌ CLIENT_SECRET JSON 형식 오류")
                            return
                    except:
                        print("❌ CLIENT_SECRET 파싱 실패")
                        return
                else:
                    # 별도로 저장된 경우
                    client_id = os.getenv('YOUTUBE_CLIENT_ID')
                    client_secret_value = client_secret
                
                if not client_id:
                    print("❌ YOUTUBE_CLIENT_ID가 필요합니다.")
                    print("📝 Google Cloud Console에서 OAuth 클라이언트 ID를 확인하세요.")
                    return
                
                if refresh_token:
                    # Refresh Token으로 인증
                    self.credentials = Credentials(
                        token=None,
                        refresh_token=refresh_token,
                        token_uri='https://oauth2.googleapis.com/token',
                        client_id=client_id,
                        client_secret=client_secret_value,
                        scopes=self.SCOPES
                    )
                    self.credentials.refresh(Request())
                else:
                    print("❌ YOUTUBE_REFRESH_TOKEN이 필요합니다.")
                    return
            
            # 토큰 저장
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, 'wb') as token:
                pickle.dump(self.credentials, token)
        
        # YouTube API 클라이언트 생성
        self.youtube = build('youtube', 'v3', credentials=self.credentials)
        print("✅ YouTube API 인증 완료")
    
    def upload_short(self, video_path, title, description):
        """
        YouTube Shorts 업로드
        
        Args:
            video_path: 업로드할 비디오 파일 경로
            title: 비디오 제목
            description: 비디오 설명
            
        Returns:
            업로드된 비디오 URL 또는 None
        """
        if not self.youtube:
            print("❌ YouTube API 인증 실패")
            return None
        
        try:
            # Shorts 식별을 위한 설명 추가
            full_description = f"{description}\n\n#Shorts"
            
            # 비디오 메타데이터
            body = {
                'snippet': {
                    'title': title,
                    'description': full_description,
                    'tags': ['Shorts', '숏폼', '밈', '짤', '재미', 'AAGAG'],
                    'categoryId': '23'  # Comedy 카테고리
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # 비디오 업로드
            media = MediaFileUpload(
                str(video_path),
                mimetype='video/*',
                resumable=True,
                chunksize=1024*1024
            )
            
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            print(f"📤 업로드 중: {title}")
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"   진행률: {progress}%")
            
            video_id = response['id']
            video_url = f"https://www.youtube.com/shorts/{video_id}"
            
            print(f"✅ 업로드 완료: {video_url}")
            return video_url
            
        except Exception as e:
            print(f"❌ 업로드 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
