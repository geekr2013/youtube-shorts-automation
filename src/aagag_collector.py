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
        """
        한글 텍스트 정규화 (NFC 정규화 + 안전 처리)
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정규화된 텍스트
        """
        if not text:
            return ""
        
        # NFC 정규화 (한글 조합형 통일)
        normalized = unicodedata.normalize('NFC', text)
        
        # 제어 문자 제거
        normalized = ''.join(char for char in normalized if unicodedata.category(char)[0] != 'C')
        
        return normalized.strip()
    
    def _safe_filename(self, text: str, max_length: int = 50) -> str:
        """
        안전한 파일명 생성 (한글 보존)
        
        Args:
            text: 원본 텍스트
            max_length: 최대 길이
            
        Returns:
            안전한 파일명
        """
        # 1. 한글 정규화
        text = self._normalize_korean_text(text)
        
        # 2. 파일 시스템 금지 문자 제거 (Windows/Linux 호환)
        forbidden_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe_text = re.sub(forbidden_chars, '', text)
        
        # 3. 연속 공백을 하나로
        safe_text = re.sub(r'\s+', ' ', safe_text)
        
        # 4. 앞뒤 공백 및 점 제거
        safe_text = safe_text.strip('. ')
        
        # 5. 길이 제한 (바이트 기준이 아닌 문자 기준)
        if len(safe_text) > max_length:
            safe_text = safe_text[:max_length].strip()
        
        # 6. 빈 문자열 방지
        if not safe_text:
            safe_text = f"video_{int(time.time())}"
        
        return safe_text
    
    def collect_and_download(self, max_videos: int = 5) -> List[Dict]:
        """
        게시물 수집 및 다운로드 (갤러리 지원)
        
        Args:
            max_videos: 최대 수집 개수
            
        Returns:
            다운로드된 비디오 정보 리스트
        """
        logger.info("\n" + "="*60)
        logger.info(f"🚀 AAGAG 비디오/GIF 수집 시작 (최대 {max_videos}개)")
        logger.info("="*60 + "\n")
        
        collected_videos = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # 1. 메인 페이지에서 게시물 링크 수집
                logger.info("📡 AAGAG 메인 페이지 크롤링 시작...")
                page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                
                # 게시물 링크 추출 (모든 게시물)
                post_links = page.eval_on_selector_all(
                    'a.article, a.article.t',
                    'elements => elements.map(e => e.href)'
                )
                
                logger.info(f"✅ 발견한 게시물 링크: {len(post_links)}개\n")
                
                # 2. 각 게시물 방문하여 모든 다운로드 링크 확인
                checked_count = 0
                for post_url in post_links:
                    if len(collected_videos) >= max_videos:
                        break
                    
                    checked_count += 1
                    logger.info(f"🔍 [{checked_count}/{len(post_links)}] 게시물 확인 중")
                    logger.info(f"   {post_url}")
                    
                    try:
                        # 게시물 상세 페이지 방문
                        page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(1500)
                        
                        # 모든 미디어 URL 추출 (갤러리 지원)
                        media_urls = self._extract_all_media_urls(page)
                        
                        if media_urls:
                            logger.info(f"   📦 발견한 미디어: {len(media_urls)}개")
                            
                            # 각 미디어 처리
                            for idx, media_url in enumerate(media_urls):
                                if len(collected_videos) >= max_videos:
                                    break
                                
                                # 이미 다운로드한 URL 스킵
                                if media_url in self.downloaded_urls:
                                    logger.debug(f"   ⏭️ 이미 다운로드함: {media_url}")
                                    continue
                                
                                file_ext = self._get_file_extension(media_url)
                                
                                if file_ext in ['.mp4', '.gif']:
                                    # 제목 생성 (여러 개인 경우 번호 추가)
                                    base_title = self._extract_title(page, media_url)
                                    if len(media_urls) > 1:
                                        title = f"{base_title}_{idx+1}"
                                    else:
                                        title = base_title
                                    
                                    logger.info(f"   ✅ [{idx+1}/{len(media_urls)}] {title} ({file_ext})")
                                    
                                    # 다운로드
                                    video_path = self._download_file(media_url, title, file_ext)
                                    
                                    if video_path:
                                        # GIF → MP4 변환
                                        if file_ext == '.gif':
                                            video_path = self._convert_gif_to_mp4(video_path)
                                        
                                        collected_videos.append({
                                            'title': title,
                                            'video_path': str(video_path),
                                            'source_url': post_url,
                                            'download_url': media_url,
                                            'type': file_ext
                                        })
                                        
                                        # 이력에 추가
                                        self.downloaded_urls.add(media_url)
                                        self._save_history()
                            
                            logger.info("")  # 빈 줄
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
        """
        게시물 페이지에서 모든 미디어 URL 추출 (갤러리 지원)
        
        Returns:
            미디어 URL 리스트 (중복 제거됨)
        """
        media_urls = []
        
        try:
            # 방법 1: <img> 태그에서 i.aagag.com 이미지/GIF 찾기
            img_sources = page.eval_on_selector_all(
                'img',
                '''elements => elements
                    .map(e => e.src)
                    .filter(src => src && src.includes('i.aagag.com'))
                '''
            )
            
            for src in img_sources:
                # 썸네일/미니 이미지 제외, 실제 파일만
                if '/mini/' not in src and '/200x170/' not in src:
                    # .jpg를 .gif나 .mp4로 변환 시도
                    if src.endswith('.jpg'):
                        # 같은 파일명의 .gif와 .mp4 시도
                        base_url = src.rsplit('.', 1)[0]
                        media_urls.append(f"{base_url}.gif")
                        media_urls.append(f"{base_url}.mp4")
                    else:
                        media_urls.append(src)
            
            # 방법 2: 페이지 소스에서 직접 i.aagag.com 링크 찾기
            content = page.content()
            
            # MP4 패턴
            mp4_pattern = r'https://i\.aagag\.com/[A-Za-z0-9]+\.mp4'
            mp4_matches = re.findall(mp4_pattern, content)
            media_urls.extend(mp4_matches)
            
            # GIF 패턴
            gif_pattern = r'https://i\.aagag\.com/[A-Za-z0-9]+\.gif'
            gif_matches = re.findall(gif_pattern, content)
            media_urls.extend(gif_matches)
            
            # 방법 3: <a> 태그의 href 확인
            links = page.eval_on_selector_all(
                'a',
                '''elements => elements
                    .map(e => e.href)
                    .filter(href => href && href.includes('i.aagag.com') && 
                           (href.endsWith('.mp4') || href.endsWith('.gif')))
                '''
            )
            media_urls.extend(links)
            
            # 중복 제거 및 정렬
            unique_urls = list(dict.fromkeys(media_urls))
            
            # 실제 존재 여부 확인 (HEAD 요청)
            valid_urls = []
            for url in unique_urls:
                if self._check_url_exists(url):
                    valid_urls.append(url)
            
            return valid_urls
        
        except Exception as e:
            logger.debug(f"미디어 URL 추출 실패: {e}")
            return []
    
    def _check_url_exists(self, url: str) -> bool:
        """URL이 실제로 존재하는지 확인 (HEAD 요청)"""
        try:
            import requests
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code == 200
        except:
            return False
    
    def _get_file_extension(self, url: str) -> str:
        """URL에서 파일 확장자 추출"""
        match = re.search(r'\.(mp4|gif|webm|avi)(?:\?|$)', url.lower())
        return f".{match.group(1)}" if match else ""
    
    def _extract_title(self, page, download_url: str) -> str:
        """제목 추출 (페이지 제목 또는 파일명) - 한글 안전 처리"""
        try:
            # 방법 1: 페이지 제목
            title = page.title()
            if title and title != "AAGAG":
                # 불필요한 접미사 제거
                title = re.sub(r'\s*-\s*AAGAG.*$', '', title)
                # 안전한 파일명으로 변환
                return self._safe_filename(title, max_length=50)
            
            # 방법 2: URL에서 파일명 추출
            filename = download_url.split('/')[-1].split('?')[0]
            return re.sub(r'\.(mp4|gif)$', '', filename)
        
        except:
            return f"video_{int(time.time())}"
    
    def _download_file(self, url: str, title: str, ext: str) -> Optional[Path]:
        """파일 다운로드 - 한글 안전 처리"""
        try:
            import requests
            
            # 안전한 파일명 생성 (한글 보존)
            safe_title = self._safe_filename(title)
            filename = f"{safe_title}{ext}"
            filepath = self.download_dir / filename
            
            # 파일명 중복 방지
            counter = 1
            while filepath.exists():
                filename = f"{safe_title}_{counter}{ext}"
                filepath = self.download_dir / filename
                counter += 1
            
            logger.info(f"      📥 다운로드 중: {filename}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # UTF-8로 안전하게 저장
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            size_mb = len(response.content) / 1024 / 1024
            logger.info(f"      ✅ 완료: {filepath.name} ({size_mb:.2f} MB)")
            return filepath
        
        except Exception as e:
            logger.error(f"      ❌ 다운로드 실패: {e}")
            return None
    
    def _convert_gif_to_mp4(self, gif_path: Path) -> Path:
        """GIF를 MP4로 변환 - 원본 음성 보존"""
        try:
            import subprocess
            
            mp4_path = gif_path.with_suffix('.mp4')
            
            logger.info(f"      🔄 GIF → MP4 변환 중...")
            
            # YouTube Shorts 호환 설정
            cmd = [
                'ffmpeg',
                '-i', str(gif_path),
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'medium',
                '-crf', '23',
                '-movflags', '+faststart',
                '-y',
                str(mp4_path)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # 원본 GIF 삭제
            gif_path.unlink()
            
            logger.info(f"      ✅ 변환 완료: {mp4_path.name}")
            return mp4_path
        
        except Exception as e:
            logger.error(f"      ❌ GIF 변환 실패: {e}")
            return gif_path


def main():
    """테스트용 메인 함수"""
    collector = AAGAGCollector()
    videos = collector.collect_and_download(max_videos=3)
    
    print(f"\n수집된 비디오: {len(videos)}개")
    for video in videos:
        print(f"  - {video['title']}: {video['video_path']}")


if __name__ == "__main__":
    main()
