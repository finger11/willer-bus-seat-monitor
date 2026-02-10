import sys
import json
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://willer-travel.com/ko/bus_search/yamanashi/all/tokyo/ikebukuro/day_18/?stockNumberMale=1&stockNumberFemale=1&rid=3&lang=ko"
TARGET_LABEL = "0106편"
THRESHOLD = 2

def to_int_safe(s: str) -> int | None:
    s = (s or "").strip()
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None

def main() -> int:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    result = {
        "ok": True,
        "checked_at": now,
        "target": TARGET_LABEL,
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

            # JS 렌더링 대기
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except PWTimeoutError:
                pass

            # 핵심 셀렉터가 DOM에 뜰 때까지 대기
            page.wait_for_selector("span.bin-ttl-box-number.bin-name", timeout=60000)

            # "0106편" 요소 찾기 (정확히 일치)
            bus = page.locator("span.bin-ttl-box-number.bin-name", has_text=TARGET_LABEL).first

            if bus.count() == 0:
                # 혹시 공백/표기 차이 대비(포함 검색)
                bus = page.locator("span.bin-ttl-box-number.bin-name", has_text="0106").first

            if bus.count() == 0:
                result["ok"] = False
                result["note"] = "DOM에서 '0106편' 요소(span.bin-ttl-box-number.bin-name)를 찾지 못했다."
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            # 버스번호가 있는 '카드/행' 컨테이너를 잡고 그 안의 vacancy-num을 찾는다.
            # 페이지 구조가 달라도 동작하도록 조상 중 가까운 블록을 탐색한다.
            container = bus.locator(
                "xpath=ancestor::*[.//span[contains(@class,'vacancy-num')]][1]"
            )

            if container.count() == 0:
                result["ok"] = False
                result["note"] = "0106편 컨테이너에서 vacancy-num을 포함한 상위 요소를 찾지 못했다."
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            vac = container.locator("span.vacancy-num").first
            if vac.count() == 0:
                result["ok"] = False
                result["note"] = "0106편 컨테이너에서 span.vacancy-num을 찾지 못했다."
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            vac_text = vac.inner_text().strip()
            seats = to_int_safe(vac_text)

            result["available_seats"] = seats

            if seats is None:
                result["ok"] = False
                result["note"] = f"vacancy-num 텍스트를 숫자로 파싱 실패: '{vac_text}'"
            else:
                result["meets_threshold"] = seats >= THRESHOLD

            browser.close()

    except Exception as e:
        result["ok"] = False
        result["note"] = f"렌더링/파싱 실패: {type(e).__name__}: {e}"

    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())


