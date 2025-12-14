import re
import os
import time
import json
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

class AagagCollector:
    def __init__(self):
        self.base_url = 'https://aagag.com/issue/'
        self.history_file = 'data/download_history.json'
        self.downloaded_ids = self._load_history()
    
    def _load_history(self):
        """다운로드 이력 로드"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            return set()
        except:
            return set()
    
    def _save_history(self):
        """다운로드 이력 저장"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.downloaded_ids), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 이력 저장 실패: {str(e)}")
    
    def get_video_posts(self, limit=20):
        """비디오 게시물 목록 수집"""
        print(f"🔍 AAGAG 게시물 수집 중...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(self.base_url, wait_until='networkidle', timeout=30000)
                time.sleep(2)
                
                # 게시물 링크 추출
                posts = []
                links = page.query_selector_all('a.article')
                
                for link in links[:limit]:
                    try:
                        href = link.get_attribute('href')
                        text = link.inner_text()
                        
                        # idx 추출
                        match = re.search(r'idx=(\d+)', href)
                        if not match:
                            continue
                        
                        idx = match.group(1)
                        
                        # 이미 다운로드한 게시물 건너뛰기
                        if idx in self.downloaded_ids:
                            continue
                        
                        # 제목과 메타데이터 파싱
                        lines = text.strip().split('\n')
                        title = lines[0] if lines else ''
                        
                        # 비디오 게시물 필터링 (.gif, .mp4 포함 또는 파일 크기가 큰 경우)
                        is_video = any(ext in title.lower() for ext in ['.gif', '.mp4', '.webm', '.mov'])
                        
                        # 파일 크기 체크 (보통 영상은 0.5MB 이상)
                        if not is_video:
                            size_match = re.search(r'([\d.]+)\s*MB', text)
                            if size_match:
                                size_mb = float(size_match.group(1))
                                is_video = size_mb >= 0.5
                        
                        if is_video:
                            posts.append({
                                'idx': idx,
                                'title': title,
                                'url': f"{self.base_url}?idx={idx}",
                                'raw_text': text
                            })
                    
                    except Exception as e:
                        print(f"⚠️ 게시물 파싱 실패: {str(e)}")
                        continue
                
                browser.close()
                print(f"✅ 총 {len(posts)}개 비디오 게시물 발견")
                return posts
            
            except Exception as e:
                print(f"❌ 페이지 로드 실패: {str(e)}")
                browser.close()
                return []
    
    def extract_media_url(self, post_url):
        """상세 페이지에서 실제 미디어 URL 추출"""
        print(f"🔍 미디어 URL 추출 중: {post_url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(post_url, wait_until='networkidle', timeout=30000)
                time.sleep(2)
                
                # video 태그 확인
                video_element = page.query_selector('video source')
                if video_element:
                    media_url = video_element.get_attribute('src')
                    if media_url:
                        # 상대 URL을 절대 URL로 변환
                        if media_url.startswith('//'):
                            media_url = 'https:' + media_url
                        elif media_url.startswith('/'):
                            media_url = 'https://aagag.com' + media_url
                        
                        browser.close()
                        print(f"✅ 비디오 URL 발견: {media_url}")
                        return media_url
                
                # img 태그 확인 (GIF)
                img_element = page.query_selector('img[src*=".gif"], img[src*=".mp4"]')
                if img_element:
                    media_url = img_element.get_attribute('src')
                    if media_url:
                        if media_url.startswith('//'):
                            media_url = 'https:' + media_url
                        elif media_url.startswith('/'):
                            media_url = 'https://aagag.com' + media_url
                        
                        browser.close()
                        print(f"✅ 이미지 URL 발견: {media_url}")
                        return media_url
                
                browser.close()
                print(f"⚠️ 미디어 URL을 찾을 수 없음")
                return None
            
            except Exception as e:
                print(f"❌ 미디어 추출 실패: {str(e)}")
                browser.close()
                return None
    
    def download_video(self, media_url, idx, output_dir='data/videos'):
        """비디오 다운로드"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 파일 확장자 결정
            ext = '.mp4'
            if '.gif' in media_url.lower():
                ext = '.gif'
            elif '.webm' in media_url.lower():
                ext = '.webm'
            
            output_path = os.path.join(output_dir, f'aagag_{idx}{ext}')
            
            print(f"📥 다운로드 중: {media_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://aagag.com/'
            }
            
            response = requests.get(media_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 다운로드 이력에 추가
            self.downloaded_ids.add(idx)
            self._save_history()
            
            print(f"✅ 다운로드 완료: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"❌ 다운로드 실패: {str(e)}")
            return None
