"""
AAGAG 콘텐츠 수집기 - 최종 안정 버전
제목 필터링 없이 모든 게시물의 실제 다운로드 링크 확인
"""

import os
import re
import time
from pathlib import Path
from typing import List, Dict, Optional
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AAGAGCollector:
    """AAGAG 사이트 크롤러 - 실제 다운로드 링크 기반"""
    
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
                with open(self.history_file, 'r') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def _save_history(self):
        """다운로드 이력 저장"""
        import json
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(list(self.downloaded_urls), f, indent=2)
    
    def collect_and_download(self, max_videos: int = 5) -> List[Dict]:
        """
        게시물 수집 및 다운로드
        
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
                
                logger.info(f"✅ 발견한 게시물 링크: {len(post_links)}개")
                
                # 2. 각 게시물 방문하여 실제 다운로드 링크 확인
                checked_count = 0
                for post_url in post_links:
                    if len(collected_videos) >= max_videos:
                        break
                    
                    # 이미 다운로드한 게시물 스킵
                    if post_url in self.downloaded_urls:
                        continue
                    
                    checked_count += 1
                    logger.info(f"🔍 [{checked_count}/{len(post_links)}] 게시물 확인 중: {post_url}")
                    
                    try:
                        # 게시물 상세 페이지 방문
                        page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(1000)
                        
                        # 실제 다운로드 링크 찾기
                        download_url = self._extract_download_url(page)
                        
                        if download_url:
                            # MP4 또는 GIF인지 확인
                            file_ext = self._get_file_extension(download_url)
                            
                            if file_ext in ['.mp4', '.gif']:
                                # 제목 추출 (게시물 페이지의 실제 제목)
                                title = self._extract_title(page, download_url)
                                
                                logger.info(f"✅ 발견: {title} ({file_ext})")
                                
                                # 다운로드
                                video_path = self._download_file(download_url, title, file_ext)
                                
                                if video_path:
                                    # GIF → MP4 변환
                                    if file_ext == '.gif':
                                        video_path = self._convert_gif_to_mp4(video_path)
                                    
                                    collected_videos.append({
                                        'title': title,
                                        'video_path': str(video_path),
                                        'source_url': post_url,
                                        'download_url': download_url,
                                        'type': file_ext
                                    })
                                    
                                    # 이력에 추가
                                    self.downloaded_urls.add(post_url)
                                    self._save_history()
                            else:
                                logger.debug(f"⏭️ 스킵 (지원하지 않는 형식): {file_ext}")
                        else:
                            logger.debug(f"⏭️ 스킵 (다운로드 링크 없음)")
                    
                    except Exception as e:
                        logger.warning(f"⚠️ 게시물 처리 실패: {e}")
                        continue
                
                logger.info(f"\n✅ 비디오/GIF 게시물 {len(collected_videos)}개 수집 완료")
                
            except Exception as e:
                logger.error(f"❌ 크롤링 오류: {e}")
            
            finally:
                browser.close()
        
        return collected_videos
    
    def _extract_download_url(self, page) -> Optional[str]:
        """게시물 페이지에서 실제 다운로드 URL 추출"""
        try:
            # 방법 1: i.aagag.com 직접 링크 찾기
            links = page.eval_on_selector_all(
                'a',
                'elements => elements.map(e => e.href)'
            )
            
            for link in links:
                if 'i.aagag.com' in link and (link.endswith('.mp4') or link.endswith('.gif')):
                    return link
            
            # 방법 2: 페이지 소스에서 정규식으로 찾기
            content = page.content()
            patterns = [
                r'https://i\.aagag\.com/[A-Za-z0-9]+\.(mp4|gif)',
                r'href="(https://i\.aagag\.com/[^"]+\.(mp4|gif))"',
                r"src='(https://i\.aagag\.com/[^']+\.(mp4|gif))'"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group(1) if match.lastindex else match.group(0)
            
            return None
        
        except Exception as e:
            logger.debug(f"다운로드 URL 추출 실패: {e}")
            return None
    
    def _get_file_extension(self, url: str) -> str:
        """URL에서 파일 확장자 추출"""
        match = re.search(r'\.(mp4|gif|webm|avi)(?:\?|$)', url.lower())
        return f".{match.group(1)}" if match else ""
    
    def _extract_title(self, page, download_url: str) -> str:
        """제목 추출 (페이지 제목 또는 파일명)"""
        try:
            # 방법 1: 페이지 제목
            title = page.title()
            if title and title != "AAGAG":
                # 불필요한 접미사 제거
                title = re.sub(r'\s*-\s*AAGAG.*$', '', title)
                # 파일명으로 사용 불가능한 문자 제거
                title = re.sub(r'[<>:"/\\|?*]', '', title)
                return title.strip()[:50]  # 최대 50자
            
            # 방법 2: URL에서 파일명 추출
            filename = download_url.split('/')[-1].split('?')[0]
            return re.sub(r'\.(mp4|gif)$', '', filename)
        
        except:
            return f"video_{int(time.time())}"
    
    def _download_file(self, url: str, title: str, ext: str) -> Optional[Path]:
        """파일 다운로드"""
        try:
            import requests
            
            # 안전한 파일명 생성
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
            filename = f"{safe_title}{ext}"
            filepath = self.download_dir / filename
            
            # 파일명 중복 방지
            counter = 1
            while filepath.exists():
                filename = f"{safe_title}_{counter}{ext}"
                filepath = self.download_dir / filename
                counter += 1
            
            logger.info(f"📥 다운로드 중: {filename}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"✅ 다운로드 완료: {filepath} ({len(response.content) / 1024 / 1024:.2f} MB)")
            return filepath
        
        except Exception as e:
            logger.error(f"❌ 다운로드 실패: {e}")
            return None
    
    def _convert_gif_to_mp4(self, gif_path: Path) -> Path:
        """GIF를 MP4로 변환"""
        try:
            import subprocess
            
            mp4_path = gif_path.with_suffix('.mp4')
            
            logger.info(f"🔄 GIF → MP4 변환 중: {gif_path.name}")
            
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
            
            logger.info(f"✅ 변환 완료: {mp4_path.name}")
            return mp4_path
        
        except Exception as e:
            logger.error(f"❌ GIF 변환 실패: {e}")
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
