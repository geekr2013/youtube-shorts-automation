import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
import time
import json

class AAGAGCollector:
    def __init__(self):
        self.base_url = "https://aagag.com/issue/"
        self.download_dir = Path('data/videos')
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = Path('data/download_history.json')
        self.downloaded_ids = self._load_history()
    
    def _load_history(self):
        """다운로드 기록 로드"""
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()
    
    def _save_history(self):
        """다운로드 기록 저장"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.downloaded_ids), f, ensure_ascii=False, indent=2)
    
    def collect_posts(self, max_posts=20):
        """AAGAG 게시물 목록 수집"""
        print(f"🔍 AAGAG 크롤링 시작: {self.base_url}")
        posts = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 메인 페이지 접속
                page.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
                
                # 게시물 링크 수집
                post_links = page.query_selector_all('a.list-group-item')
                print(f"📋 발견된 게시물: {len(post_links)}개")
                
                for i, link in enumerate(post_links[:max_posts]):
                    try:
                        # 게시물 URL 추출
                        href = link.get_attribute('href')
                        if not href or '?idx=' not in href:
                            continue
                        
                        post_id = href.split('?idx=')[1].split('&')[0]
                        
                        # 이미 다운로드한 게시물은 스킵
                        if post_id in self.downloaded_ids:
                            print(f"⏭️  [{i+1}] 이미 다운로드됨: {post_id}")
                            continue
                        
                        # 제목 추출
                        title_elem = link.query_selector('.subject')
                        title = title_elem.inner_text().strip() if title_elem else f"AAGAG_{post_id}"
                        
                        post_url = f"https://aagag.com{href}" if href.startswith('/') else href
                        
                        posts.append({
                            'id': post_id,
                            'title': title,
                            'url': post_url
                        })
                        
                        print(f"✅ [{i+1}] {title}")
                        
                    except Exception as e:
                        print(f"⚠️  게시물 파싱 실패: {str(e)}")
                        continue
                
                browser.close()
                
        except Exception as e:
            print(f"❌ 크롤링 오류: {str(e)}")
        
        print(f"\n📊 수집 완료: {len(posts)}개 (신규)")
        return posts
    
    def download_video(self, post):
        """게시물에서 비디오 다운로드"""
        post_id = post['id']
        post_url = post['url']
        
        print(f"\n📥 다운로드 시작: {post['title']}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 게시물 페이지 접속
                page.goto(post_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
                
                # 비디오 URL 추출 (video 태그의 src)
                video_element = page.query_selector('video source')
                if not video_element:
                    video_element = page.query_selector('video')
                
                if not video_element:
                    print(f"❌ 비디오 요소를 찾을 수 없음")
                    browser.close()
                    return None
                
                video_url = video_element.get_attribute('src')
                if not video_url:
                    print(f"❌ 비디오 URL을 찾을 수 없음")
                    browser.close()
                    return None
                
                # 상대 경로를 절대 경로로 변환
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                elif video_url.startswith('/'):
                    video_url = 'https://i.aagag.com' + video_url
                
                print(f"🎬 비디오 URL: {video_url}")
                
                browser.close()
                
                # 비디오 다운로드
                response = requests.get(video_url, stream=True, timeout=30)
                response.raise_for_status()
                
                # 파일 저장
                file_extension = '.mp4'
                if '.webm' in video_url:
                    file_extension = '.webm'
                
                video_path = self.download_dir / f"{post_id}{file_extension}"
                
                with open(video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = video_path.stat().st_size / (1024 * 1024)
                print(f"✅ 다운로드 완료: {video_path.name} ({file_size:.2f} MB)")
                
                # 다운로드 기록 저장
                self.downloaded_ids.add(post_id)
                self._save_history()
                
                return video_path
                
        except Exception as e:
            print(f"❌ 다운로드 실패: {str(e)}")
            return None
