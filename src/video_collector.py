def download_video(self, video_id, output_dir='data/videos'):
    """동영상 다운로드 - OAuth 방식"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f'{video_id}.mp4')
        
        if os.path.exists(output_path):
            print(f"✅ 이미 다운로드됨: {video_id}")
            return output_path
            
        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            # OAuth 인증 사용
            'username': 'oauth2',
            'password': '',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Referer': 'https://www.youtube.com/',
            },
            # 추가 옵션
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        print(f"📥 다운로드 시작: {video_id}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
        
        print(f"✅ 다운로드 완료: {video_id}")
        return output_path
        
    except Exception as e:
        print(f"❌ 다운로드 실패 ({video_id}): {str(e)}")
        return None
