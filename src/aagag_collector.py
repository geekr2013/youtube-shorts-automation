"""
AAGAG 콘텐츠 수집기 - 갤러리 페이지 지원 + 한글 인코딩 강화 버전
여러 개의 비디오/GIF가 있는 경우 모두 수집
"""

import os
import re
import time
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AAGAGCollector:
    """AAGAG 사이트 크롤러 - 갤러리 지원 + 한글 안전 처리"""
    
    def __init__(self, base_url: str = "https://aagag.com/issue/"):
        self.base_url = base_url
        self.download_dir = Path("data/videos")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # 다운로드 이력 관리
        self.history_file = Path("data/download_history.json")
        self.downloaded_urls = self._load_history()
    
    def _load_history(self) -> set:
        """다운로드 이력 로드"""
        if self.history_file.exists():
            import json
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def _save_history(self):
        """다운로드 이력 저장"""
        import json
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.downloaded_urls), f, indent=2, ensure_ascii=False)
    
    def _normalize_korean_text(self, text: str) -> str:
        """한글 텍스트 정규화"""
        if not text:
            return ""
        normalized = unicodedata.normalize('NFC', text)
        normalized = ''.join(char for char in normalized if unicodedata.category(char)[0] != 'C')
        return normalized.strip()
    
    def _safe_filename(self, text: str, max_length: int = 50) -> str:
        """안전한 파일명 생성 (특수문자 및 마침표 제거 강화)"""
        text = self._normalize_korean_text(text)
        # 1. 파일명에서 확장자로 오인될 수 있는 마침표나 특수문자 제거
        safe_text = re.sub(r'[\.!\?]', '', text) 
        forbidden_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe_text = re.sub(forbidden_chars, '', safe_text)
        # 2. 공백을 언더바로 변경하여 FFmpeg 에러 방지
        safe_text = re.sub(r'\s+', '_', safe_text)
        safe_text = safe_text.strip('_')
        
        if len(safe_text) > max_length:
            safe_text = safe_text[:max_length].strip('_')
        
        if not safe_text:
            safe_text = f"video_{int(time.time())}"
        
        return safe_text
    
    def collect_and_download(self, max_videos: int = 5) -> List[Dict]:
        """게시물 수집 및 다운로드"""
        logger.info("\n" + "="*60)
        logger.info(f"🚀 AAGAG 비디오/GIF 수집 시작 (최대 {max_videos}개)")
        logger.info("="*60 + "\n")
        
        collected_videos = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                logger.info("📡 AAGAG 메인 페이지 크롤링 시작...")
                page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                
                post_links = page.eval_on_selector_all(
                    'a.article, a.article.t',
                    'elements => elements.map(e => e.href)'
                )
                
                logger.info(f"✅ 발견한 게시물 링크: {len(post_links)}개\n")
                
                checked_count = 0
                for post_url in post_links:
                    if len(collected_videos) >= max_videos:
                        break
                    
                    checked_count += 1
                    logger.info(f"🔍 [{checked_count}/{len(post_links)}] 게시물 확인 중")
                    logger.info(f"   {post_url}")
                    
                    try:
                        page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(1500)
                        
                        media_urls = self._extract_all_media_urls(page)
                        
                        if media_urls:
                            logger.info(f"   📦 발견한 미디어: {len(media_urls)}개")
                            
                            for idx, media_url in enumerate(media_urls):
                                if len(collected_videos) >= max_videos:
                                    break
                                
                                if media_url in self.downloaded_urls:
                                    continue
                                
                                file_ext = self._get_file_extension(media_url)
                                
                                if file_ext in ['.mp4', '.gif']:
                                    base_title = self._extract_title(page, media_url)
                                    title = f"{base_title}_{idx+1}" if len(media_urls) > 1 else base_title
                                    
                                    logger.info(f"   ✅ [{idx+1}/{len(media_urls)}] {title} ({file_ext})")
                                    video_path = self._download_file(media_url, title, file_ext)
                                    
                                    if video_path:
                                        if file_ext == '.gif':
                                            video_path = self._convert_gif_to_mp4(video_path)
                                        
                                        collected_videos.append({
                                            'title': title,
                                            'video_path': str(video_path),
                                            'source_url': post_url,
                                            'download_url': media_url,
                                            'type': file_ext
                                        })
                                        self.downloaded_urls.add(media_url)
                                        self._save_history()
                            logger.info("")
                        else:
                            logger.debug(f"   ⏭️ 스킵 (미디어 없음)\n")
                    except Exception as e:
                        logger.warning(f"   ⚠️ 게시물 처리 실패: {e}\n")
                        continue
                logger.info(f"✅ 비디오/GIF 게시물 {len(collected_videos)}개 수집 완료\n")
            except Exception as e:
                logger.error(f"❌ 크롤링 오류: {e}\n")
            finally:
                browser.close()
        return collected_videos
    
    def _extract_all_media_urls(self, page) -> List[str]:
        media_urls = []
        try:
            img_sources = page.eval_on_selector_all(
                'img',
                'elements => elements.map(e => e.src).filter(src => src && src.includes("i.aagag.com"))'
            )
            for src in img_sources:
                if '/mini/' not in src and '/200x170/' not in src:
                    if src.endswith('.jpg'):
                        base_url = src.rsplit('.', 1)[0]
                        media_urls.append(f"{base_url}.gif")
                        media_urls.append(f"{base_url}.mp4")
                    else:
                        media_urls.append(src)
            
            content = page.content()
            media_urls.extend(re.findall(r'https://i\.aagag\.com/[A-Za-z0-9]+\.mp4', content))
            media_urls.extend(re.findall(r'https://i\.aagag\.com/[A-Za-z0-9]+\.gif', content))
            
            unique_urls = list(dict.fromkeys(media_urls))
            return [url for url in unique_urls if self._check_url_exists(url)]
        except:
            return []
    
    def _check_url_exists(self, url: str) -> bool:
        try:
            import requests
            return requests.head(url, timeout=5).status_code == 200
        except: return False
    
    def _get_file_extension(self, url: str) -> str:
        match = re.search(r'\.(mp4|gif|webm|avi)(?:\?|$)', url.lower())
        return f".{match.group(1)}" if match else ""
    
    def _extract_title(self, page, download_url: str) -> str:
        try:
            title = page.title()
            if title and title != "AAGAG":
                title = re.sub(r'\s*-\s*AAGAG.*$', '', title)
                # .jpg 등 파일명에 포함된 불필요한 확장자 문자열 제거
                title = re.sub(r'\.jpg|\.png|\.gif|\.mp4', '', title, flags=re.IGNORECASE)
                return self._safe_filename(title)
            filename = download_url.split('/')[-1].split('?')[0]
            return re.sub(r'\.(mp4|gif)$', '', filename)
        except:
            return f"video_{int(time.time())}"
    
    def _download_file(self, url: str, title: str, ext: str) -> Optional[Path]:
        try:
            import requests
            safe_title = self._safe_filename(title)
            filename = f"{safe_title}{ext}"
            filepath = self.download_dir / filename
            
            counter = 1
            while filepath.exists():
                filename = f"{safe_title}_{counter}{ext}"
                filepath = self.download_dir / filename
                counter += 1
            
            logger.info(f"      📥 다운로드 중: {filename}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # 파일이 제대로 다운로드 되었는지(크기 체크) 확인
            if filepath.stat().st_size < 100: # 100바이트 미만은 실패로 간주
                 logger.error(f"      ❌ 다운로드 파일 손상됨")
                 filepath.unlink()
                 return None

            return filepath
        except Exception as e:
            logger.error(f"      ❌ 다운로드 실패: {e}")
            return None
    
    def _convert_gif_to_mp4(self, gif_path: Path) -> Path:
        try:
            import subprocess
            mp4_path = gif_path.with_suffix('.mp4')
            cmd = [
                'ffmpeg', '-i', str(gif_path),
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(mp4_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            gif_path.unlink()
            return mp4_path
        except:
            return gif_path
