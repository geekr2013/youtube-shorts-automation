import os
import json
import requests
import time
import subprocess
import re
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin


class AAGAGCollector:
    """AAGAG 사이트에서 비디오/GIF를 수집하는 클래스"""
    
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
    
    def extract_title_and_type(self, raw_text):
        """
        원본 텍스트에서 제목과 파일 타입 추출
        
        예: "재미있어 보이는 에어홀 놀이.gif2.3 MB767010124시간전"
        -> ("재미있어 보이는 에어홀 놀이", "gif")
        
        Args:
            raw_text: 원본 게시물 텍스트
            
        Returns:
            tuple: (제목, 파일타입) 또는 (None, None)
        """
        # .mp4 또는 .gif 패턴 찾기 (대소문자 무시)
        mp4_match = re.search(r'(.+?)\.mp4', raw_text, re.IGNORECASE)
        gif_match = re.search(r'(.+?)\.gif', raw_text, re.IGNORECASE)
        
        if mp4_match:
            title = mp4_match.group(1).strip()
            return (title, "mp4")
        elif gif_match:
            title = gif_match.group(1).strip()
            return (title, "gif")
        
        return (None, None)
    
    def collect_posts(self, max_posts=50):
        """
        AAGAG 메인 페이지에서 게시물 링크 수집
        
        Args:
            max_posts: 수집할 최대 게시물 수
            
        Returns:
            list: 게시물 정보 리스트 [{"url": "...", "title": "...", "type": "mp4|gif"}]
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
                        raw_text = link.inner_text().strip()
                        
                        if href and raw_text:
                            full_url = urljoin(self.base_url, href)
                            
                            # 제목과 파일 타입 추출
                            title, file_type = self.extract_title_and_type(raw_text)
                            
                            if title and file_type:
                                posts.append({
                                    "url": full_url,
                                    "title": f"{title}.{file_type}",  # 확장자 포함
                                    "type": file_type
                                })
                                
                                emoji = "🎬" if file_type == "mp4" else "🖼️"
                                print(f"  {emoji} [{file_type.upper()}] {title[:40]}...")
                                
                    except Exception as e:
                        print(f"  ⚠️ 게시물 파싱 실패: {e}")
                        continue
                
                print(f"✅ 비디오/GIF 게시물 {len(posts)}개 수집 완료")
                
            except Exception as e:
                print(f"❌ 크롤링 오류: {e}")
            finally:
                browser.close()
        
        return posts
    
    def get_media_download_url(self, post_url, media_type):
        """
        개별 게시물 페이지에서 실제 미디어 다운로드 URL 추출
        
        Args:
            post_url: 게시물 페이지 URL
            media_type: 'mp4' or 'gif'
            
        Returns:
            str: 미디어 다운로드 URL (없으면 None)
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # 게시물 페이지 방문
                page.goto(post_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=10000)
                
                if media_type == "mp4":
                    # MP4: i.aagag.com/*.mp4 패턴
                    download_links = page.locator("a[href*='i.aagag.com'][href$='.mp4']").all()
                    
                    if download_links:
                        media_url = download_links[0].get_attribute("href")
                        print(f"    ✅ MP4 URL 발견: {media_url}")
                        browser.close()
                        return media_url
                    
                    # 정규식 백업
                    content = page.content()
                    if "i.aagag.com" in content and ".mp4" in content:
                        pattern = r'https://i\.aagag\.com/[A-Za-z0-9]+\.mp4'
                        matches = re.findall(pattern, content)
                        if matches:
                            media_url = matches[0]
                            print(f"    ✅ MP4 URL 발견 (정규식): {media_url}")
                            browser.close()
                            return media_url
                
                elif media_type == "gif":
                    # GIF: i.aagag.com/*.gif 패턴
                    download_links = page.locator("a[href*='i.aagag.com'][href$='.gif']").all()
                    
                    if download_links:
                        media_url = download_links[0].get_attribute("href")
                        print(f"    ✅ GIF URL 발견: {media_url}")
                        browser.close()
                        return media_url
                    
                    # 정규식 백업
                    content = page.content()
                    if "i.aagag.com" in content and ".gif" in content:
                        pattern = r'https://i\.aagag\.com/[A-Za-z0-9]+\.gif'
                        matches = re.findall(pattern, content)
                        if matches:
                            media_url = matches[0]
                            print(f"    ✅ GIF URL 발견 (정규식): {media_url}")
                            browser.close()
                            return media_url
                
                print(f"    ⚠️ {media_type.upper()} URL을 찾을 수 없습니다")
                
            except Exception as e:
                print(f"    ❌ 게시물 페이지 파싱 오류: {e}")
            finally:
                browser.close()
        
        return None
    
    def convert_gif_to_mp4(self, gif_path):
        """
        GIF 파일을 MP4로 변환
        
        Args:
            gif_path: GIF 파일 경로
            
        Returns:
            str: 변환된 MP4 파일 경로 (실패 시 None)
        """
        mp4_path = gif_path.replace('.gif', '.mp4')
        
        try:
            print(f"    🔄 GIF → MP4 변환 중...")
            
            # ffmpeg로 GIF를 MP4로 변환 (고품질 설정)
            cmd = [
                'ffmpeg',
                '-i', gif_path,
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # 짝수 크기로 조정
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-y',  # 덮어쓰기
                mp4_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(mp4_path):
                file_size = os.path.getsize(mp4_path) / (1024 * 1024)
                print(f"    ✅ 변환 완료: {os.path.basename(mp4_path)} ({file_size:.2f} MB)")
                
                # 원본 GIF 삭제
                os.remove(gif_path)
                return mp4_path
            else:
                print(f"    ❌ 변환 실패: {result.stderr.decode()[:200]}")
                return None
                
        except Exception as e:
            print(f"    ❌ GIF 변환 오류: {e}")
            return None
    
    def download_media(self, media_url, title, media_type):
        """
        미디어 다운로드 (MP4 또는 GIF)
        
        Args:
            media_url: 미디어 다운로드 URL
            title: 미디어 제목
            media_type: 'mp4' or 'gif'
            
        Returns:
            str: 다운로드된 파일 경로 (실패 시 None)
        """
        # 파일명 정리 (확장자 제거)
        clean_title = title.replace('.mp4', '').replace('.MP4', '').replace('.gif', '').replace('.GIF', '')
        # 파일명에서 특수문자 제거
        clean_title = "".join(c for c in clean_title if c.isalnum() or c in (' ', '-', '_', '(', ')', '[', ']'))
        clean_title = clean_title.strip()[:100]  # 최대 100자
        
        # 원본 확장자로 다운로드
        extension = '.gif' if media_type == 'gif' else '.mp4'
        filename = f"{clean_title}{extension}"
        filepath = os.path.join(self.download_dir, filename)
        
        try:
            print(f"    ⬇️ 다운로드 중: {filename}")
            response = requests.get(media_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
            print(f"    ✅ 다운로드 완료: {filename} ({file_size:.2f} MB)")
            
            # GIF인 경우 MP4로 변환
            if media_type == 'gif':
                mp4_path = self.convert_gif_to_mp4(filepath)
                if mp4_path:
                    return mp4_path
                else:
                    # 변환 실패 시 원본 GIF 삭제
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return None
            
            return filepath
            
        except Exception as e:
            print(f"    ❌ 다운로드 실패: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
    
    def collect_and_download(self, max_videos=5):
        """
        게시물 수집 및 미디어 다운로드
        
        Args:
            max_videos: 다운로드할 최대 비디오 수
            
        Returns:
            list: 다운로드된 비디오 정보 [{"path": "...", "title": "..."}]
        """
        print(f"\n{'='*60}")
        print(f"🚀 AAGAG 비디오/GIF 수집 시작 (최대 {max_videos}개)")
        print(f"{'='*60}\n")
        
        # 1. 게시물 수집
        posts = self.collect_posts(max_posts=max_videos * 3)  # 여유있게 수집
        
        if not posts:
            print("⚠️ 수집된 게시물이 없습니다.")
            return []
        
        # 2. 미디어 다운로드
        downloaded_videos = []
        
        for i, post in enumerate(posts):
            if len(downloaded_videos) >= max_videos:
                print(f"\n✅ 목표 개수({max_videos}개) 달성, 수집 종료")
                break
            
            post_url = post["url"]
            title = post["title"]
            media_type = post["type"]
            
            # 이미 다운로드한 게시물인지 확인
            post_id = post_url.split("idx=")[-1] if "idx=" in post_url else post_url
            if post_id in self.downloaded_ids:
                print(f"\n[{i+1}/{len(posts)}] ⏭️ 이미 다운로드한 게시물: {title[:50]}...")
                continue
            
            emoji = "🎬" if media_type == "mp4" else "🖼️"
            print(f"\n[{i+1}/{len(posts)}] {emoji} [{media_type.upper()}] 처리 중: {title[:50]}...")
            
            # 3. 미디어 다운로드 URL 추출
            media_url = self.get_media_download_url(post_url, media_type)
            
            if not media_url:
                print(f"    ⏭️ 건너뛰기 (미디어 URL 없음)")
                continue
            
            # 4. 미디어 다운로드 (GIF는 자동으로 MP4 변환)
            filepath = self.download_media(media_url, title, media_type)
            
            if filepath:
                downloaded_videos.append({
                    "path": filepath,
                    "title": title.replace('.mp4', '').replace('.MP4', '').replace('.gif', '').replace('.GIF', '')
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
