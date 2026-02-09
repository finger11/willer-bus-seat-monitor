import re
import sys
import json
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://willer-travel.com/ko/bus_search/yamanashi/all/tokyo/ikebukuro/day_18/?stockNumberMale=1&stockNumberFemale=1&rid=3&lang=ko"
TARGET_BUS_NO = "0106"
THRESHOLD = 2

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def extract_seats_from_text(text: str, bus_no: str) -> int | None:
    """
    렌더링된 본문 텍스트에서 'Bus No. 0106' 주변의 '공석 N'을 찾아 N 반환.
    """
    t = normalize_spaces(text)

    # Bus No 표기 변형 대응
    m = re.search(rf"Bus\s*No\.?\s*{re.escape(bus_no)}", t, flags=re.IGNORECASE)
    if not m:
        m = re.search(rf"Bus\s*No\.?{re.escape(bus_no)}", t, flags=re.IGNORECASE)
        if not m:
            return None

    window = t[m.start(): m.start() + 5000]

    # '공석 3' 형태
    m2 = re.search(r"공석\s*(\d+)", window)
    if m2:
        return int(m2.group(1))

    return None

def main() -> int:
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
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            context = browser.new_context(
                locale="ko-KR",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                viewport={"width": 1280, "height": 2000},
            )
            page = context.new_page()

            page.goto(URL, wait_until="domcontentloaded", timeout=60000)

            # 네트워크 idle 대기(안 떨어질 수 있으므로 예외 허용)
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except PWTimeoutError:
                pass

            # 텍스트에 Bus No가 등장할 때까지 추가 대기
            try:
                page.wait_for_function(
                    "() => document.body && document.body.innerText && document.body.innerText.includes('Bus No')",
                    timeout=20000,
                )
            except PWTimeoutError:
                pass

            body_text = page.inner_text("body")
            browser.close()

        seats = extract_seats_from_text(body_text, TARGET_BUS_NO)
        result["available_seats"] = seats

        if seats is None:
            result["ok"] = False
            result["note"] = "렌더링 후에도 버스번호(0106) 또는 공석 정보를 찾지 못했다. 표기/구조가 변경되었을 수 있다."
        else:
            result["meets_threshold"] = seats >= THRESHOLD

    except Exception as e:
        result["ok"] = False
        result["note"] = f"렌더링/파싱 실패: {type(e).__name__}: {e}"

    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
