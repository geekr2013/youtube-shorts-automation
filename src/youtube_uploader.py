import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeUploader:
    """YouTube API를 사용한 비디오 업로드"""
    
    def __init__(self):
        self.youtube = None
        self.token_file = "data/youtube_token.pickle"
    
    def authenticate(self):
        """YouTube API 인증"""
        try:
            creds = None
            
            # 저장된 토큰 로드
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
            
            # 토큰이 없거나 만료된 경우 갱신
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # 환경 변수에서 인증 정보 가져오기
                    client_id = os.getenv("YOUTUBE_CLIENT_ID")
                    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
                    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
                    
                    if not all([client_id, client_secret, refresh_token]):
                        print("❌ YouTube API 인증 정보가 환경 변수에 없습니다.")
                        return False
                    
                    creds = Credentials(
                        token=None,
                        refresh_token=refresh_token,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=client_id,
                        client_secret=client_secret
                    )
                    creds.refresh(Request())
                
                # 토큰 저장
                os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)
            
            # YouTube API 클라이언트 생성
            self.youtube = build('youtube', 'v3', credentials=creds)
            return True
            
        except Exception as e:
            print(f"❌ YouTube API 인증 오류: {e}")
            return False
    
    def upload_video(self, video_path, title, description=""):
        """
        YouTube에 비디오 업로드
        
        Args:
            video_path: 업로드할 비디오 파일 경로
            title: 비디오 제목
            description: 비디오 설명
            
        Returns:
            bool: 업로드 성공 여부
        """
        try:
            if not self.youtube:
                print("❌ YouTube API가 인증되지 않았습니다.")
                return False
            
            if not os.path.exists(video_path):
                print(f"❌ 비디오 파일을 찾을 수 없습니다: {video_path}")
                return False
            
            # 업로드 요청 본문
            request_body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'categoryId': '22'  # People & Blogs
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # 미디어 파일
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # 업로드 실행
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=request_body,
                media_body=media
            )
            
            response = request.execute()
            
            video_id = response.get('id')
            if video_id:
                print(f"  ✅ 업로드 완료! 비디오 ID: {video_id}")
                print(f"  🔗 링크: https://youtube.com/shorts/{video_id}")
                return True
            else:
                print("  ❌ 비디오 ID를 가져올 수 없습니다.")
                return False
                
        except Exception as e:
            print(f"  ❌ 업로드 오류: {e}")
            return False
