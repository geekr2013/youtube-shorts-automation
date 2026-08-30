# HANA Pilates Real-Video Shorts Automation

무료 Mixkit 촬영 세션에서 같은 성인 동양인 주 모델의 실제 연속동작만 선별해, 미국·글로벌용 영어 필라테스 쇼츠를 제작하고 YouTube에 공개합니다. 유료 영상 생성 서비스와 배경음악은 사용하지 않습니다.

## 현재 운영 형식

- 활성 모델: `mixkit-sports-center-peach-v1`
- 영상: 1080×1920 실제 MP4, 세 동작, 약 20~46초
- 구도: 장면별로 검수한 전신·상체·복부·하체 확대 중심을 고정
- 자막: 영어 전용 Lato, 반투명 차콜 패널, 장면에 따라 상단 또는 하단 안전영역 사용
- 음성: 자연스러운 미국 영어 여성 안내 음성. Gemini TTS를 우선 사용하고 무료 Edge 신경망 음성을 예비로 사용
- 음악: 설명을 방해하거나 저품질로 들리는 문제를 피하기 위해 없음
- 설명: 영어 동작명·횟수·안전 안내·Mixkit 원본 페이지·라이선스 표시
- 공개 확인: 업로드 응답만 믿지 않고 `public` 상태와 YouTube 처리 완료를 다시 조회

## 모델·원본 고정

- `assets/instructor/mixkit-sports-center-peach-v1.json`에 정확한 원본 ID, 페이지, 다운로드 주소, SHA-256, 길이, 해상도, 구도 좌표와 사람 검수 메모를 저장
- 현재 공개 풀은 서로 겹치지 않는 원본 9개와 루틴 3개
- 원본 바이트, 해상도, 길이, 제공처, 모델 ID 또는 검수 승인이 하나라도 달라지면 공개 중단
- 복숭아색 운동복의 같은 주 모델을 중심에 두며, 트레이너나 수업 참가자는 배경에만 남을 수 있음
- 원본 MP4는 저장소에 복제하지 않고 실행 때 Mixkit에서 받아 해시를 확인
- `assets/instructor/hana-reference-v2.png`는 fictional visual direction only이며 특정 실존 인물의 얼굴을 복제하지 않음
- 기존 포즈 참고 이미지는 카탈로그 검사에만 사용하며 공개 영상 원본이 아님

## 자동 운영

- GitHub Actions가 매일 UTC 01:35에 실행하며 PC가 꺼져 있어도 동작
- 예약 실행은 GitHub 사정에 따라 실제 시작 시각이 늦어질 수 있음
- 코드 변경은 기본적으로 건식 실행만 수행하고, 예약 실행·수동 공개 실행만 실제 업로드
- `YOUTUBE_PRIVACY=public`, 언어 `en`, 대상 `US/global`
- 공개한 루틴과 원본은 제목이나 순서만 바꿔 다시 사용하지 않음
- 검수된 신규 원본이 소진되면 다른 모델 또는 반복 영상으로 자동 대체하지 않고 실패 종료
- 최종 MP4, 메타데이터, 화면표는 실행 결과에 3일간 보관

## 편집 원칙

- 첫 프레임부터 움직임 시작
- 세 동작 번호, 한 줄 자세 포인트, 숫자 횟수만 표시
- 음성에서는 숫자를 자연스러운 영어 단어로 읽음
- 얼굴·목표 근육·관절과 YouTube 하단 제목 및 오른쪽 버튼이 겹치지 않도록 장면별 자막 위치 적용
- 자연스러운 피부 질감은 유지하고 과한 하이라이트와 색 편차만 약하게 보정
- 저장 유도 마무리와 루틴별 영어 질문을 포함
- 의료·감량·체형 변화 보장 문구, 타 채널 영상·문구·음원 복제 금지

## 인기 영상 참고 범위

YouTube Data API가 있으면 최근 미국 영어 필라테스 쇼츠의 공개 반응 신호를 기록합니다. 다른 채널을 복제하지 않고, 첫 프레임 동작·짧은 번호형 루틴·가독성 높은 자막·저장 유도 같은 일반 편집 원칙에만 사용합니다. 분석값은 참고 자료이며 노출이나 수익을 보장하지 않습니다.

## GitHub Secrets

| 이름 | 용도 |
| --- | --- |
| `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` | 자연스러운 영어 안내 음성 |
| `YOUTUBE_CLIENT_ID` | YouTube OAuth |
| `YOUTUBE_CLIENT_SECRET` | YouTube OAuth |
| `YOUTUBE_REFRESH_TOKEN` | 자동 업로드 권한 갱신 |
| `YOUTUBE_DATA_API_KEY` | 선택: 공개 트렌드·성과 조회 |
| `SENDER_EMAIL`, `GMAIL_PASSWORD`, `RECEIVER_EMAIL` | 선택: 성공·실패 이메일 알림 |

`PEXELS_API_KEY`와 `PIXABAY_API_KEY`는 과거 후보 검수 도구용이며 현재 Mixkit 고정 모델 공개 경로에는 필요하지 않습니다.

## 수동 검증

GitHub의 **Actions → Daily Hana Pilates Short → Run workflow**에서 실행합니다.

- `dry_run = true`: 영상과 화면표만 제작
- `dry_run = false`: 검증된 설정으로 YouTube 공개 업로드

## 한계와 리스크

- 무료·동일 모델·실제 동작·권리 추적을 동시에 지키는 원본은 유한합니다. 현재 세 개의 고유 루틴을 소진한 뒤에는 새 원본 검수 전까지 업로드가 멈춥니다.
- 동일 촬영 세션의 실제 주 모델을 고정한 것이며, 사용자가 제공한 참고 이미지의 얼굴을 합성·복제한 생성형 인물이 아닙니다.
- 교육적 해설과 편집을 더해도 YouTube 재사용 콘텐츠 또는 수익화 심사 통과는 보장되지 않습니다.
- 조회수, 추천 노출, 구독자, 수익은 보장할 수 없습니다. 공개 후 시청 유지율·반복 재생·저장·댓글로 판단해야 합니다.
- 화면표 검수는 오류를 줄이지만 자격 있는 필라테스 지도자의 개별 지도를 대체하지 않습니다.

## 개발 확인

```bash
pip install -r requirements.txt
python -m compileall -q src
python -m unittest discover -s tests -v
python src/main.py --check-config --dry-run
python src/main.py --dry-run
```
