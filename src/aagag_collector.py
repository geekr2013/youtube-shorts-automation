import os
import json
import requests
import time
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin


class AAGAGCollector:
    """AAGAG 사이트에서 비디오를 수집하는 클래스"""
    
    def __init__(self, download_dir="downloads", history_file="data/download_history.json"):
        self.download_dir = download_dir
        self.history_file = history_file
        self.base_url = "https://aagag.com"
        self.downloaded_ids = self.load_history()
        
        # 다운로드 디렉토리 생성
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
    
    def load_history(self):
        """다운로드 히스토리 로드"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def save_history(self):
        """다운로드 히스토리 저장"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.downloaded_ids), f, ensure_ascii=False, indent=2)
    
    def collect_posts(self, max_posts=50):
        """
        AAGAG 메인 페이지에서 게시물 링크 수집
        
        Args:
            max_posts: 수집할 최대 게시물 수
            
        Returns:
            list: 게시물 정보 리스트 [{"url": "...", "title": "..."}]
        """
        print(f"📡 AAGAG 메인 페이지 크롤링 시작...")
        posts = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # 메인 페이지 방문
                page.goto(self.base_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=30000)
                
                # 게시물 링크 수집 (a.article 또는 a.article.t 셀렉터)
                article_links = page.locator("a.article, a.article.t").all()
                
                print(f"✅ 발견한 게시물 링크: {len(article_links)}개")
                
                for link in article_links[:max_posts]:
                    try:
                        href = link.get_attribute("href")
                        title = link.inner_text().strip()
                        
                        if href and title:
                            full_url = urljoin(self.base_url, href)
                            
                            # .mp4 파일만 필터링
                            if title.lower().endswith('.mp4'):
                                posts.append({
                                    "url": full_url,
                                    "title": title
                                })
                                print(f"  🎬 {title[:50]}... ({full_url})")
                    except Exception as e:
                        print(f"  ⚠️ 게시물 파싱 실패: {e}")
                        continue
                
                print(f"✅ .mp4 비디오 게시물 {len(posts)}개 수집 완료")
                
            except Exception as e:
                print(f"❌ 크롤링 오류: {e}")
            finally:
                browser.close()
        
        return posts
    
    def get_video_download_url(self, post_url):
        """
        개별 게시물 페이지에서 실제 비디오 다운로드 URL 추출
        
        Args:
            post_url: 게시물 페이지 URL
            
        Returns:
            str: 비디오 다운로드 URL (없으면 None)
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # 게시물 페이지 방문
                page.goto(post_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=10000)
                
                # 다운로드 링크 찾기 (https://i.aagag.com/*.mp4 패턴)
                # 방법 1: a 태그에서 .mp4 링크 찾기
                download_links = page.locator("a[href*='i.aagag.com'][href$='.mp4']").all()
                
                if download_links:
                    video_url = download_links[0].get_attribute("href")
                    print(f"    ✅ 비디오 URL 발견: {video_url}")
                    browser.close()
                    return video_url
                
                # 방법 2: 페이지 소스에서 i.aagag.com 링크 찾기
                content = page.content()
                if "i.aagag.com" in content and ".mp4" in content:
                    import re
                    pattern = r'https://i\.aagag\.com/[A-Za-z0-9]+\.mp4'
                    matches = re.findall(pattern, content)
                    if matches:
                        video_url = matches[0]
                        print(f"    ✅ 비디오 URL 발견 (정규식): {video_url}")
                        browser.close()
                        return video_url
                
                print(f"    ⚠️ 비디오 URL을 찾을 수 없습니다")
                
            except Exception as e:
                print(f"    ❌ 게시물 페이지 파싱 오류: {e}")
            finally:
                browser.close()
        
        return None
    
    def download_video(self, video_url, title):
        """
        비디오 다운로드
        
        Args:
            video_url: 비디오 다운로드 URL
            title: 비디오 제목
            
        Returns:
            str: 다운로드된 파일 경로 (실패 시 None)
        """
        # 파일명 정리 (확장자 제거 후 .mp4 추가)
        clean_title = title.replace('.mp4', '').replace('.MP4', '')
        # 파일명에서 특수문자 제거
        clean_title = "".join(c for c in clean_title if c.isalnum() or c in (' ', '-', '_', '(', ')', '[', ']'))
        clean_title = clean_title.strip()[:100]  # 최대 100자
        
        filename = f"{clean_title}.mp4"
        filepath = os.path.join(self.download_dir, filename)
        
        try:
            print(f"    ⬇️ 다운로드 중: {filename}")
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
            print(f"    ✅ 다운로드 완료: {filename} ({file_size:.2f} MB)")
            return filepath
            
        except Exception as e:
            print(f"    ❌ 다운로드 실패: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
    
    def collect_and_download(self, max_videos=5):
        """
        게시물 수집 및 비디오 다운로드
        
        Args:
            max_videos: 다운로드할 최대 비디오 수
            
        Returns:
            list: 다운로드된 비디오 정보 [{"path": "...", "title": "..."}]
        """
        print(f"\n{'='*60}")
        print(f"🚀 AAGAG 비디오 수집 시작 (최대 {max_videos}개)")
        print(f"{'='*60}\n")
        
        # 1. 게시물 수집
        posts = self.collect_posts(max_posts=max_videos * 3)  # 여유있게 수집
        
        if not posts:
            print("⚠️ 수집된 게시물이 없습니다.")
            return []
        
        # 2. 비디오 다운로드
        downloaded_videos = []
        
        for i, post in enumerate(posts):
            if len(downloaded_videos) >= max_videos:
                print(f"\n✅ 목표 개수({max_videos}개) 달성, 수집 종료")
                break
            
            post_url = post["url"]
            title = post["title"]
            
            # 이미 다운로드한 게시물인지 확인
            post_id = post_url.split("idx=")[-1] if "idx=" in post_url else post_url
            if post_id in self.downloaded_ids:
                print(f"\n[{i+1}/{len(posts)}] ⏭️ 이미 다운로드한 게시물: {title[:50]}...")
                continue
            
            print(f"\n[{i+1}/{len(posts)}] 🎬 처리 중: {title[:50]}...")
            
            # 3. 비디오 다운로드 URL 추출
            video_url = self.get_video_download_url(post_url)
            
            if not video_url:
                print(f"    ⏭️ 건너뛰기 (비디오 URL 없음)")
                continue
            
            # 4. 비디오 다운로드
            filepath = self.download_video(video_url, title)
            
            if filepath:
                downloaded_videos.append({
                    "path": filepath,
                    "title": title.replace('.mp4', '').replace('.MP4', '')
                })
                
                # 히스토리에 추가
                self.downloaded_ids.add(post_id)
                self.save_history()
            
            # 서버 부하 방지를 위한 지연
            time.sleep(2)
        
        print(f"\n{'='*60}")
        print(f"✅ 수집 완료: 총 {len(downloaded_videos)}개 비디오 다운로드")
        print(f"{'='*60}\n")
        
        return downloaded_videos


if __name__ == "__main__":
    # 테스트 실행
    collector = AAGAGCollector()
    videos = collector.collect_and_download(max_videos=3)
    
    print("\n📋 다운로드된 비디오:")
    for video in videos:
        print(f"  - {video['title']}")
        print(f"    경로: {video['path']}")
