"""환경 변수로 전달된 비밀값의 흔한 붙여넣기 형식을 정리한다."""


def clean_secret(value: str) -> str:
    cleaned = str(value or "").strip()
    for prefix in (
        "YOUTUBE_CLIENT_ID=",
        "YOUTUBE_CLIENT_SECRET=",
        "YOUTUBE_REFRESH_TOKEN=",
        "client_id=",
        "client_secret=",
        "refresh_token=",
    ):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1].strip()
    return cleaned

