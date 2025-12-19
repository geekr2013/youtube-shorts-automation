# 🎬 AAGAG YouTube Shorts Automation (2025 Optimized)

이 프로젝트는 **AAGAG** 커뮤니티의 핫한 콘텐츠를 자동으로 수집하여, 시청자에게 최적화된 **YouTube Shorts** 포맷으로 가공하고 업로드하는 자동화 파이프라인입니다. 

PO/PM 관점에서 **최소 운영 비용으로 최대의 CTR(클릭률)과 도달율**을 확보할 수 있도록 설계되었습니다.

---

## 🏗 시스템 구조 (Architecture)

본 시스템은 크게 4단계의 모듈형 파이프라인으로 작동합니다.

1. **Content Discovery**: Playwright 기반의 웹 크롤링을 통해 트렌디한 영상/GIF 수집
2. **Video Engine**: FFmpeg을 활용한 9:16 세로형 변환, 자막 합성, 썸네일 추출
3. **AI SEO**: 영상 제목을 기반으로 알고리즘에 최적화된 메타데이터(제목, 태그) 생성
4. **Auto-Publish**: YouTube Data API v3를 통한 자동 업로드 및 알림 발송

---

## 📂 파일 트리 및 역할 설명

| 분류 | 파일/폴더 명 | 역할 및 기능 설명 |
| :--- | :--- | :--- |
| **Workflow** | `.github/workflows/daily-upload.yml` | **자동화의 심장.** 매일 지정된 시간에 GitHub Actions를 가동시키는 스케줄러. |
| **Core Source** | `src/main.py` | **메인 관제소.** 모든 모듈을 순서대로 실행하고 파일 삭제 등의 정리를 담당. |
| | `src/aagag_collector.py` | **콘텐츠 수집기.** 유효한 영상 주소를 추출하고 한글 파일명을 정규화하여 저장. |
| | `src/youtube_uploader.py` | **배포 관리자.** OAuth 인증을 통해 실제 유튜브 채널에 영상을 업로드. |
| | `src/background_music.py` | **사운드 편집.** 영상의 분위기를 살려줄 배경음악을 합성 (현재 선택 사항). |
| | `src/email_notifier.py` | **운영 보고서.** 작업 완료 후 업로드 성공 여부를 이메일로 리포트. |
| **Assets** | `font/SeoulAlrim-ExtraBold.otf` | **브랜드 가이드.** 자막의 가독성을 높여주는 서울알림체 볼드 폰트. |
| **Data Storage** | `data/download_history.json` | **중복 방지.** 이미 업로드한 영상의 ID를 기록하여 동일 영상 업로드 방지. |
| | `data/youtube_token.pickle` | **인증 저장소.** 매번 로그인할 필요 없도록 유지되는 YouTube API 토큰. |
| **Settings** | `requirements.txt` | **환경 구성.** 프로젝트 실행에 필요한 파이썬 라이브러리 목록. |

---

## ⚙️ 작동 원리 (Workflow)



### 1. 콘텐츠 수집 (Collection)
`aagag_collector.py`가 AAGAG 사이트의 게시물을 분석합니다. 단순 이미지는 제외하고, MP4 비디오와 GIF(자동 변환) 파일만 골라내어 서버에 임시 저장합니다. 이때 파일명에 포함된 특수문자를 제거하여 FFmpeg 처리 에러를 사전에 방지합니다.

### 2. 쇼츠 최적화 가공 (Processing)
`main.py`는 수집된 영상을 YouTube Shorts 규격인 **1080x1920 (9:16)**으로 강제 변환합니다. 
* 가로 영상은 시네마틱 블러 배경을 추가합니다.
* 영상 **상단**에 제목 자막을 크게(폰트 크기 80) 배치하여 시청자의 이탈을 방지합니다.
* 가장 흥미로운 지점에서 고품질 썸네일(.jpg)을 자동 추출합니다.

### 3. 유튜브 업로드 (Distribution)
`youtube_uploader.py`가 Google OAuth 인증을 통해 채널에 접근합니다. 동영상과 썸네일을 함께 전송하며, Shorts 전용 해시태그(#shorts, #개그 등)를 자동으로 추가하여 노출 알고리즘을 태웁니다.

### 4. 사후 관리 (Management)
작업이 끝나면 서버의 저장 공간 확보를 위해 모든 임시 영상 파일을 삭제하며, 성공한 리스트를 운영자의 이메일로 발송합니다.

---

## 🛠 필수 설정 사항 (Secrets)

GitHub Actions 환경 변수(Secrets)에 다음 정보가 등록되어 있어야 정상 작동합니다.

* `YOUTUBE_CLIENT_SECRET`: Google Cloud 데스크톱 앱용 JSON 전체 내용
* `YOUTUBE_REFRESH_TOKEN`: 영구 인증용 리프레시 토큰
* `GMAIL_USERNAME` / `GMAIL_PASSWORD`: 알림 발송용 Gmail 계정 정보
* `NOTIFICATION_EMAIL`: 보고서를 받을 이메일 주소

---
