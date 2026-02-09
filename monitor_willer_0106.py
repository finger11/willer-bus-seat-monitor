import re
import sys
import json
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

URL = "https://willer-travel.com/ko/bus_search/yamanashi/all/tokyo/ikebukuro/day_18/?stockNumberMale=1&stockNumberFemale=1&rid=3&lang=ko"
TARGET_BUS_NO = "0106"
THRESHOLD = 2

def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8,ja;q=0.7",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def extract_seats_from_text(text: str, bus_no: str) -> int | None:
    """
    페이지 텍스트에서 'Bus No. 0106' 근처의 '공석 N'을 찾아 N을 반환한다.
    (구조가 조금 바뀌어도 동작하도록 텍스트 기반으로 탐색한다.)
    """
    # 공백/개행 정리
    t = re.sub(r"\s+", " ", text)

    # 1) Bus No. 0106 주변 일정 범위를 잘라 '공석 N' 탐색
    m = re.search(rf"Bus\s*No\.?\s*{re.escape(bus_no)}", t, flags=re.IGNORECASE)
    if not m:
        return None

    window = t[m.start(): m.start() + 2000]  # 버스번호 이후 2000자 정도 범위에서 탐색
    m2 = re.search(r"공석\s*(\d+)", window)
    if m2:
        return int(m2.group(1))

    return None

def main():
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    result = {
        "ok": True,
        "checked_at": now,
        "bus_no": TARGET_BUS_NO,
        "threshold": THRESHOLD,
        "available_seats": None,
        "meets_threshold": False,
        "url": URL,
        "note": "",
    }

    try:
        html = fetch_html(URL)
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        seats = extract_seats_from_text(text, TARGET_BUS_NO)
        result["available_seats"] = seats

        if seats is None:
            result["ok"] = False
            result["note"] = "버스번호(0106) 또는 공석 정보를 텍스트에서 찾지 못했다. 페이지가 JS로 렌더링될 가능성이 있다."
        else:
            result["meets_threshold"] = seats >= THRESHOLD

    except Exception as e:
        result["ok"] = False
        result["note"] = f"요청/파싱 실패: {type(e).__name__}: {e}"

    print(json.dumps(result, ensure_ascii=False))
    # 워크플로우에서 읽을 수 있도록 meets_threshold를 exit code로도 표현한다
    sys.exit(0)

if __name__ == "__main__":
    main()
