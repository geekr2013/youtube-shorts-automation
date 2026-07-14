# Original Knowledge Shorts Automation

타인의 인기 영상을 다시 올리던 기존 방식을 중단하고, **원본 한국어 지식 쇼츠를 하루 1편 자동 제작·업로드**하는 무료 MVP입니다.

## 무엇이 달라졌나

1. 한국 YouTube의 교육·과학 인기 신호를 참고합니다. 다른 영상의 제목이나 화면은 복제하지 않습니다.
2. Gemini가 안전하고 반복되지 않는 주제를 고릅니다.
3. 위키백과 공개 API에서 검증 자료를 가져오고, 그 범위 안에서 새 대본을 씁니다.
4. Pexels 또는 Pixabay의 스톡 영상, 한국어 AI 내레이션, 직접 만든 자막으로 9:16 영상을 만듭니다.
5. YouTube에 하루 1편 공개하고, 기존 영상의 조회·좋아요·댓글 성과를 다음 주제 선택에 반영합니다.
6. 출처와 영상 제공자를 설명란에 자동 표시하고, 합성 콘텐츠 여부도 YouTube에 공개합니다.

이 구조는 저작권 위험과 재사용 콘텐츠 위험을 크게 낮추지만, 조회수·수익·수익화 승인을 보장하지는 않습니다. 실제 수익 발생에는 YouTube 파트너 프로그램 조건 충족과 채널 심사가 별도로 필요합니다.

## 운영 시간

- 매일 한국 시간 오후 7시 35분
- GitHub Actions에서 실행되므로 개인 PC가 꺼져 있어도 동작
- 한 번에 1편만 올려 반복·대량 업로드 위험을 줄임
- 실패 시 GitHub Actions가 빨간색으로 표시되고, 이메일 설정이 있으면 알림 발송

## 사용 중인 GitHub Secrets

현재 저장소에 등록된 아래 이름을 그대로 사용합니다. 비밀값은 코드나 로그에 저장하지 않습니다.

| 이름 | 용도 |
| --- | --- |
| `GEMINI_API_KEY` | 주제 선정과 원본 대본 작성 |
| `YOUTUBE_DATA_API_KEY` | 인기 신호와 영상 성과 확인 |
| `PEXELS_API_KEY` | 스톡 영상 검색 |
| `PIXABAY_API_KEY` | Pexels 실패 시 대체 영상 검색 |
| `YOUTUBE_CLIENT_ID` | YouTube OAuth 인증 |
| `YOUTUBE_CLIENT_SECRET` | YouTube OAuth 인증 |
| `YOUTUBE_REFRESH_TOKEN` | 자동 업로드 권한 갱신 |
| `SENDER_EMAIL` | 선택 사항: 알림 발신 주소 |
| `GMAIL_PASSWORD` | 선택 사항: Gmail 앱 비밀번호 |
| `RECEIVER_EMAIL` | 선택 사항: 알림 수신 주소 |

## 자동 안전장치

- 최근 주제와 78% 이상 유사하면 업로드 중단
- 정치, 사건사고, 연예인, 의료·투자 조언 등 고위험 주제 차단
- 과장 표현, 출처 없는 내용, 너무 짧거나 긴 대본 차단
- 서로 다른 스톡 영상이 2개 미만이면 업로드 중단
- 검증 자료와 출처 URL이 없으면 업로드 중단
- 내레이션과 최종 영상 길이를 자동 확인
- AI 음성 사용을 `containsSyntheticMedia`로 공개

## 수동 점검 방법

GitHub 저장소의 **Actions → Daily Original Knowledge Short → Run workflow**에서 실행할 수 있습니다.

- `dry_run = true`: 영상만 만들고 업로드하지 않음
- `dry_run = false`: 실제 공개 업로드

실행 결과의 `short-preview-...` 파일은 3일 동안만 보관됩니다. 공개된 영상 기록과 성과는 `data/published_topics.json`에 남습니다.

## 주요 정책·라이선스

- [YouTube 채널 수익화 정책](https://support.google.com/youtube/answer/1311392)
- [YouTube AI 콘텐츠 공개 안내](https://support.google.com/youtube/answer/14328491)
- [Pexels 라이선스](https://www.pexels.com/license/)
- [Pixabay 콘텐츠 라이선스](https://pixabay.com/service/license-summary/)
- [Wikipedia 저작권 안내](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)

## 개발자용 확인

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/main.py --check-config
python src/main.py --dry-run
```

영상 생성에는 FFmpeg와 나눔 글꼴이 필요합니다. GitHub Actions에서는 자동으로 설치됩니다.
