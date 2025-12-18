"""
YouTube Uploader Module - Real API Implementation
YouTube Data API v3를 사용한 실제 업로드 구현
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, Dict
import logging

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


class YouTubeUploader:
    """YouTube 업로드 클래스 - 실제 API 연동"""
    
    def __init__(self):
        """초기화 및 OAuth 인증"""
        self.authenticated = False
        self.youtube = None
        
        try:
            self._authenticate()
        except Exception as e:
            logger.warning(f"⚠️ YouTube 인증 실패: {e}")
            logger.warning("⚠️ 수집만 진행합니다")
    
    def _authenticate(self):
        """OAuth 2.0 인증"""
        creds = None
        token_pickle = Path("data/youtube_token.pickle")
        
        # 저장된 토큰 확인
        if token_pickle.exists():
            try:
                with open(token_pickle, 'rb') as token:
                    creds = pickle.load(token)
                logger.info("✅ 저장된 YouTube 토큰 로드")
            except Exception as e:
                logger.warning(f"⚠️ 토큰 로드 실패: {e}")
        
        # 토큰이 없거나 만료된 경우
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("✅ YouTube 토큰 갱신 완료")
                except Exception as e:
                    logger.error(f"❌ 토큰 갱신 실패: {e}")
                    creds = None
            
            # refresh_token 환경변수로 재생성
            if not creds:
                client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
                refresh_token = os.getenv('YOUTUBE_REFRESH_TOKEN')
                
                if not client_secret or not refresh_token:
                    raise ValueError("YOUTUBE_CLIENT_SECRET 또는 YOUTUBE_REFRESH_TOKEN 환경변수 없음")
                
                try:
                    # client_secret JSON 파싱
                    if client_secret.startswith('{'):
                        client_config = json.loads(client_secret)
                    else:
                        # 파일 경로인 경우
                        with open(client_secret, 'r') as f:
                            client_config = json.load(f)
                    
                    # Credentials 재생성
                    creds = Credentials(
                        token=None,
                        refresh_token=refresh_token,
                        token_uri=client_config['installed']['token_uri'],
                        client_id=client_config['installed']['client_id'],
                        client_secret=client_config['installed']['client_secret'],
                        scopes=SCOPES
                    )
                    
                    # 토큰 갱신
                    creds.refresh(Request())
                    logger.info("✅ 새로운 YouTube 토큰 생성 완료")
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"YOUTUBE_CLIENT_SECRET JSON 파싱 오류: {e}")
                except KeyError as e:
                    raise ValueError(f"client_secret 형식 오류: {e}")
            
            # 토큰 저장
            if creds:
                token_pickle.parent.mkdir(parents=True, exist_ok=True)
                with open(token_pickle, 'wb') as token:
                    pickle.dump(creds, token)
                logger.info(f"✅ 토큰 저장: {token_pickle}")
        
        # YouTube API 클라이언트 생성
        self.youtube = build('youtube', 'v3', credentials=creds)
        self.authenticated = True
        logger.info("✅ YouTube API 인증 완료")
    
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list = None,
        category: str = "24",  # Entertainment
        privacy: str = "public",
        thumbnail_path: Optional[str] = None
    ) -> Dict:
        """
        비디오 업로드 (실제 YouTube API 사용)
        
        Args:
            video_path: 업로드할 비디오 파일 경로
            title: 비디오 제목
            description: 비디오 설명
            tags: 태그 리스트
            category: 카테고리 ID (24=Entertainment, 22=People & Blogs)
            privacy: 공개 설정 (public/private/unlisted)
            thumbnail_path: 썸네일 이미지 경로
            
        Returns:
            업로드 결과 딕셔너리
        """
        if not self.authenticated:
            logger.error("❌ YouTube 인증 정보 없음")
            return {
                'success': False,
                'error': 'Not authenticated',
                'video_id': None
            }
        
        if not os.path.exists(video_path):
            logger.error(f"❌ 비디오 파일 없음: {video_path}")
            return {
                'success': False,
                'error': f'Video file not found: {video_path}',
                'video_id': None
            }
        
        try:
            # 파일 크기 확인
            file_size = os.path.getsize(video_path)
            size_mb = file_size / 1024 / 1024
            
            logger.info(f"📤 YouTube 업로드 시작")
            logger.info(f"   📁 파일: {os.path.basename(video_path)}")
            logger.info(f"   📊 크기: {size_mb:.2f} MB")
            logger.info(f"   📺 제목: {title}")
            
            # 제목/설명 인코딩 확인
            title_encoded = title.encode('utf-8').decode('utf-8')
            description_encoded = description.encode('utf-8').decode('utf-8')
            
            # 태그 검증 및 정리
            validated_tags = []
            if tags:
                tags_text = ','.join(tags)
                if len(tags_text) <= 500:  # YouTube 태그 총 길이 제한: 500자
                    validated_tags = tags[:15]  # 최대 15개 태그
                else:
                    # 길이 초과 시 일부만 사용
                    for tag in tags[:15]:
                        test_text = ','.join(validated_tags + [tag])
                        if len(test_text) <= 500:
                            validated_tags.append(tag)
                        else:
                            break
            
            logger.info(f"   🏷️ 태그 수: {len(validated_tags)}")
            
            # 업로드 메타데이터
            body = {
                'snippet': {
                    'title': title_encoded[:100],  # YouTube 제한: 100자
                    'description': description_encoded[:5000],  # YouTube 제한: 5000자
                    'tags': validated_tags,
                    'categoryId': category,
                    'defaultLanguage': 'ko',
                    'defaultAudioLanguage': 'ko'
                },
                'status': {
                    'privacyStatus': privacy,
                    'selfDeclaredMadeForKids': False  # madeForKids 필드 제거 (중복 방지)
                }
            }
            
            # 미디어 파일 업로드
            media = MediaFileUpload(
                video_path,
                chunksize=1024*1024,  # 1MB chunks
                resumable=True,
                mimetype='video/mp4'
            )
            
            # API 요청
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            # 업로드 실행 (resumable)
            response = None
            retry_count = 0
            max_retries = 3
            
            while response is None and retry_count < max_retries:
                try:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        logger.info(f"   ⏳ 업로드 진행: {progress}%")
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        retry_count += 1
                        logger.warning(f"   ⚠️ 서버 오류, 재시도 {retry_count}/{max_retries}")
                        continue
                    else:
                        raise
            
            if not response:
                raise Exception("업로드 응답 없음")
            
            video_id = response['id']
            video_url = f"https://www.youtube.com/shorts/{video_id}"
            
            logger.info(f"   ✅ 업로드 성공!")
            logger.info(f"   🔗 URL: {video_url}")
            
            # 썸네일 업로드 (선택사항)
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    self._upload_thumbnail(video_id, thumbnail_path)
                except Exception as e:
                    logger.warning(f"   ⚠️ 썸네일 업로드 실패: {e}")
            
            return {
                'success': True,
                'video_id': video_id,
                'video_url': video_url,
                'title': title,
                'description': description,
                'tags': tags
            }
            
        except HttpError as e:
            error_content = e.content.decode('utf-8', errors='ignore')
            error_msg = f"YouTube API 오류 {e.resp.status}: {error_content}"
            logger.error(f"❌ {error_msg}")
            
            # 400 에러의 경우 상세 정보 출력
            if e.resp.status == 400:
                logger.error(f"   📋 업로드 시도한 메타데이터:")
                logger.error(f"      제목 길이: {len(title)} 자")
                logger.error(f"      설명 길이: {len(description)} 자")
                logger.error(f"      태그 수: {len(validated_tags)}")
                logger.error(f"      파일 크기: {size_mb:.2f} MB")
            
            return {
                'success': False,
                'error': error_msg,
                'video_id': None
            }
        except Exception as e:
            logger.error(f"❌ 업로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'video_id': None
            }
    
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """썸네일 업로드"""
        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
            ).execute()
            logger.info(f"   ✅ 썸네일 업로드 성공")
        except Exception as e:
            raise Exception(f"썸네일 업로드 실패: {e}")
    
    def get_video_info(self, video_id: str) -> Optional[Dict]:
        """비디오 정보 조회"""
        if not self.authenticated:
            return None
        
        try:
            response = self.youtube.videos().list(
                part='snippet,status,statistics',
                id=video_id
            ).execute()
            
            if response['items']:
                return response['items'][0]
            return None
        except Exception as e:
            logger.error(f"❌ 비디오 정보 조회 실패: {e}")
            return None


def main():
    """테스트용 메인 함수"""
    uploader = YouTubeUploader()
    
    if uploader.authenticated:
        print("✅ YouTube 인증 성공")
    else:
        print("❌ YouTube 인증 실패")


if __name__ == "__main__":
    main()
