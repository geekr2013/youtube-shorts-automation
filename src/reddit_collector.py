import praw
import requests
import os
import json
from datetime import datetime

class RedditCollector:
    def __init__(self, client_id, client_secret, user_agent):
        """Reddit API 초기화"""
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
    def get_video_posts(self, subreddit_name='funny', limit=20):
        """비디오 게시물 수집"""
        subreddit = self.reddit.subreddit(subreddit_name)
        video_posts = []
        
        for post in subreddit.hot(limit=limit):
            # 비디오 콘텐츠만 필터링
            if self._is_video_post(post):
                video_posts.append({
                    'id': post.id,
                    'title': post.title,
                    'url': post.url,
                    'score': post.score,
                    'created': datetime.fromtimestamp(post.created_utc).isoformat(),
                    'permalink': f"https://reddit.com{post.permalink}",
                    'media_url': self._extract_media_url(post)
                })
        
        return video_posts
    
    def _is_video_post(self, post):
        """비디오 게시물 판단"""
        url = post.url.lower()
        
        # 직접 비디오 링크
        if any(ext in url for ext in ['.mp4', '.webm', '.gif', '.gifv']):
            return True
        
        # Reddit 호스팅 비디오
        if hasattr(post, 'is_video') and post.is_video:
            return True
        
        # v.redd.it 링크
        if 'v.redd.it' in url:
            return True
        
        return False
    
    def _extract_media_url(self, post):
        """실제 미디어 URL 추출"""
        try:
            # Reddit 호스팅 비디오
            if hasattr(post, 'media') and post.media:
                if 'reddit_video' in post.media:
                    return post.media['reddit_video']['fallback_url']
            
            # 직접 URL
            url = post.url
            if url.endswith('.gifv'):
                url = url.replace('.gifv', '.mp4')
            
            return url
        except:
            return post.url
    
    def download_video(self, url, output_dir='data/videos'):
        """비디오 다운로드"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            filename = os.path.basename(url.split('?')[0])
            if not filename.endswith(('.mp4', '.webm', '.gif')):
                filename += '.mp4'
            
            output_path = os.path.join(output_dir, filename)
            
            print(f"📥 다운로드 중: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ 다운로드 완료: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 다운로드 실패: {str(e)}")
            return None
