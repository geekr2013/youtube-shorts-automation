def download_video(self, video_id, output_dir='data/videos'):
    """동영상 다운로드 - Android Player Client 사용"""
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
            # Android 클라이언트 사용 (봇 탐지 우회)
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        print(f"📥 다운로드 시작 (Android Client): {video_id}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
        
        print(f"✅ 다운로드 완료: {video_id}")
        return output_path
        
    except Exception as e:
        print(f"❌ 다운로드 실패 ({video_id}): {str(e)}")
        # Fallback: iOS 클라이언트 시도
        try:
            print(f"🔄 iOS 클라이언트로 재시도: {video_id}")
            ydl_opts['extractor_args']['youtube']['player_client'] = ['ios']
            ydl_opts['http_headers']['User-Agent'] = 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            print(f"✅ iOS 클라이언트로 다운로드 완료: {video_id}")
            return output_path
        except Exception as e2:
            print(f"❌ iOS 클라이언트도 실패 ({video_id}): {str(e2)}")
            return None
