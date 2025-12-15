# 🎬 AAGAG YouTube Shorts 자동화

**AAGAG 사이트의 재미있는 짧은 영상을 자동으로 수집하여 YouTube Shorts에 업로드하는 자동화 시스템**

---

## 🎯 **주요 기능**

✅ **AAGAG 자동 크롤링** - Playwright로 최신 개그 영상 수집  
✅ **갤러리 페이지 지원** - 한 게시물에 여러 영상이 있어도 모두 수집  
✅ **Gemini AI 제목/설명 생성** - 영상 내용을 분석하여 자동 생성  
✅ **한글 완벽 지원** - UTF-8 인코딩, NFC 정규화로 한글 깨짐 방지  
✅ **GIF → MP4 자동 변환** - YouTube Shorts 호환 포맷으로 변환  
✅ **배경음악 추가** (선택) - ffmpeg로 BGM 삽입  
✅ **YouTube 자동 업로드** - YouTube Data API v3 실제 연동  
✅ **Gmail 알림** - 업로드 결과 이메일 발송  
✅ **GitHub Actions 자동 실행** - 매일 정해진 시간에 자동 실행  

---

## 📁 **프로젝트 구조**

```
youtube-shorts-automation/
├── .github/
│   └── workflows/
│       └── daily-upload.yml        # GitHub Actions 워크플로우
├── src/
│   ├── main.py                     # 메인 실행 스크립트
│   ├── aagag_collector.py          # AAGAG 크롤러 (갤러리 지원)
│   ├── youtube_uploader.py         # YouTube 업로더 (실제 API)
│   ├── content_processor_gemini.py # Gemini AI 프로세서
│   ├── background_music.py         # 배경음악 추가
│   └── email_notifier.py           # 이메일 알림
├── data/
│   ├── videos/                     # 다운로드된 비디오
│   ├── music/                      # 배경음악 파일
│   └── download_history.json       # 다운로드 이력
├── requirements.txt                # Python 패키지 목록
└── README.md
```

---

## 🚀 **설치 및 실행**

### **1. 사전 요구사항**

- Python 3.11 이상
- ffmpeg (GIF 변환 및 배경음악용)
- 한글 폰트 (자막 기능용)

### **2. 로컬 설치**

```bash
# 저장소 클론
git clone https://github.com/YOUR_USERNAME/youtube-shorts-automation.git
cd youtube-shorts-automation

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# ffmpeg 설치 (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-nanum

# ffmpeg 설치 (macOS)
brew install ffmpeg

# ffmpeg 설치 (Windows)
# https://ffmpeg.org/download.html 에서 다운로드
```

### **3. 환경 변수 설정**

`.env` 파일 생성 또는 환경 변수 설정:

```bash
# YouTube API (필수)
YOUTUBE_CLIENT_SECRET='{"installed":{"client_id":"...","client_secret":"..."}}'
YOUTUBE_REFRESH_TOKEN="your_refresh_token"

# Gemini API (필수)
GEMINI_API_KEY="your_gemini_api_key"

# Gmail 알림 (선택)
GMAIL_USERNAME="your_email@gmail.com"
GMAIL_PASSWORD="your_app_password"
NOTIFICATION_EMAIL="receiver@example.com"

# 배경음악 (선택)
ENABLE_BGM="false"  # true로 설정 시 배경음악 추가
BGM_PATH="data/music/background.mp3"
```

### **4. 로컬 실행**

```bash
python src/main.py
```

---

## 🔑 **API 키 설정 가이드**

### **1. Gemini API 키 발급**

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. `Get API Key` 클릭
3. API 키 복사 → `GEMINI_API_KEY` 환경 변수에 설정

### **2. YouTube Data API v3 설정**

#### **2-1. OAuth 2.0 클라이언트 생성**

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 > 라이브러리** → "YouTube Data API v3" 검색 및 활성화
4. **API 및 서비스 > 사용자 인증 정보** → `+ 사용자 인증 정보 만들기` → `OAuth 클라이언트 ID`
5. 애플리케이션 유형: **데스크톱 앱** 선택
6. `client_secret.json` 다운로드

#### **2-2. Refresh Token 발급**

로컬에서 한 번 실행하여 토큰 발급:

```bash
python src/youtube_uploader.py
```

- 브라우저가 열리면 Google 계정 로그인
- YouTube 업로드 권한 승인
- `data/youtube_token.pickle` 파일 생성됨
- 파일에서 `refresh_token` 추출하여 환경 변수에 설정

#### **2-3. GitHub Secrets 설정**

```
YOUTUBE_CLIENT_SECRET: client_secret.json 전체 내용 (JSON 문자열)
YOUTUBE_REFRESH_TOKEN: 발급받은 refresh_token
```

### **3. Gmail 앱 비밀번호 (선택)**

1. Google 계정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성
3. 발급받은 16자리 비밀번호를 `GMAIL_PASSWORD`에 설정

---

## ⚙️ **GitHub Actions 설정**

### **1. GitHub Secrets 설정**

Repository → Settings → Secrets and variables → Actions → New repository secret

필수:
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `GEMINI_API_KEY`

선택:
- `GMAIL_USERNAME`
- `GMAIL_PASSWORD`
- `NOTIFICATION_EMAIL`

### **2. 워크플로우 실행**

- **자동 실행**: 매일 UTC 0시 (한국 시간 오전 9시)
- **수동 실행**: Actions 탭 → "Daily GagConcert Upload" → "Run workflow"

---

## 🛠️ **문제 해결**

### **1. 수집된 게시물이 0개**

**원인**: AAGAG 사이트 HTML 구조 변경

**해결**:
```bash
# 최신 코드로 업데이트
git pull origin main

# 다운로드 이력 초기화
rm data/download_history.json
```

### **2. YouTube 업로드 실패: invalid_client**

**원인**: `YOUTUBE_CLIENT_SECRET` JSON 형식 오류

**해결**:
```bash
# client_secret.json 파일 내용 전체를 따옴표 없이 그대로 복사
# GitHub Secrets에 붙여넣기
```

### **3. 한글 깨짐**

**원인**: 인코딩 문제 또는 폰트 누락

**해결**:
```bash
# Ubuntu/Debian
sudo apt-get install fonts-nanum fonts-nanum-coding

# 폰트 캐시 갱신
sudo fc-cache -fv
```

### **4. GIF 변환 실패**

**원인**: ffmpeg 미설치

**해결**:
```bash
# ffmpeg 설치
sudo apt-get install ffmpeg

# 설치 확인
ffmpeg -version
```

### **5. Gemini API 할당량 초과**

**원인**: 무료 할당량 초과

**해결**:
- [Google AI Studio](https://makersuite.google.com/app/apikey)에서 할당량 확인
- 새 API 키 발급 또는 유료 플랜 고려

---

## 📊 **사용 예시**

### **실행 결과 예시**

```
======================================================================
🚀 AAGAG YouTube Shorts 자동화 시작
======================================================================

✅ 모듈 임포트 완료
✅ YouTube 업로더 준비 완료
✅ Gemini AI 프로세서 준비 완료

📥 AAGAG 콘텐츠 수집 시작...

============================================================
🚀 AAGAG 비디오/GIF 수집 시작 (최대 5개)
============================================================

📡 AAGAG 메인 페이지 크롤링 시작...
✅ 발견한 게시물 링크: 30개

🔍 [1/30] 게시물 확인 중
   https://aagag.com/issue/?idx=946713_1
   📦 발견한 미디어: 7개
   ✅ [1/7] 남자는_왜_일찍_죽는가_1 (.mp4)
      📥 다운로드 중: 남자는_왜_일찍_죽는가_1.mp4
      ✅ 완료: 남자는_왜_일찍_죽는가_1.mp4 (2.34 MB)

✅ 비디오/GIF 게시물 5개 수집 완료

======================================================================
🎬 [1/5] 비디오 처리 중
======================================================================

🤖 Gemini AI로 제목/설명 생성 중...
   ✅ 제목: 😂 남자는 왜 일찍 죽을까?
   ✅ 설명: 남성의 평균 수명이 여성보다 짧은 이유를 개그로...
   ✅ 태그: 개그, 재미, 웃음, 남자, 수명

📤 YouTube 업로드 중...
   📁 파일: 남자는_왜_일찍_죽는가_1.mp4
   📊 크기: 2.34 MB
   📺 제목: 😂 남자는 왜 일찍 죽을까?
   ⏳ 업로드 진행: 100%
   ✅ 업로드 성공!
   🔗 URL: https://www.youtube.com/shorts/ABC123xyz

======================================================================
🎉 모든 작업 완료!
======================================================================
```

---

## 🔒 **보안 주의사항**

❌ **절대로 커밋하지 말 것**:
- API 키 (`GEMINI_API_KEY`)
- OAuth 토큰 (`YOUTUBE_REFRESH_TOKEN`)
- Gmail 비밀번호 (`GMAIL_PASSWORD`)
- `client_secret.json`
- `data/youtube_token.pickle`

✅ **권장 사항**:
- GitHub Secrets 사용
- `.gitignore`에 민감 파일 추가
- API 키 정기적으로 갱신

---

## 📚 **기술 스택**

- **Python 3.11+**
- **Playwright** - 웹 크롤링
- **ffmpeg** - 비디오/오디오 처리
- **Google Gemini API** - AI 제목/설명 생성
- **YouTube Data API v3** - 비디오 업로드
- **Gmail SMTP** - 이메일 알림
- **GitHub Actions** - 자동 실행

---

## 📝 **최근 업데이트**

### **v2.0.0** (2024-12-15)
- ✅ YouTube Data API v3 실제 연동 (시뮬레이션 제거)
- ✅ Gemini AI 제목/설명 생성 기능 통합
- ✅ 한글 인코딩 강화 (UTF-8, NFC 정규화)
- ✅ 배경음악 추가 기능 연결
- ✅ 갤러리 페이지 다중 영상 수집 지원
- ✅ 중복 다운로드 방지 (download_history.json)
- ✅ 에러 핸들링 개선

---

## 🤝 **기여**

이슈 및 Pull Request 환영합니다!

---

## 📧 **문의**

문제가 발생하면 GitHub Issues에 남겨주세요.

---

## 📄 **라이센스**

MIT License
