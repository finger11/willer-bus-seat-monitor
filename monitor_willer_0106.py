import sys
import json
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# 모니터링 대상 URL
URL = "https://willer-travel.com/ko/bus_search/yamanashi/all/tokyo/ikebukuro/day_17/?stockNumberMale=1&stockNumberFemale=1&rid=3&lang=ko"

# 타겟 버스/임계치
TARGET_LABEL = "0106편"
THRESHOLD = 2

def to_int_safe(s: str) -> int | None:
    s = (s or "").strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None

def main() -> int:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    result = {
        "ok": True,
        "checked_at": now,
        "target": TARGET_LABEL,
        "threshold": THRESHOLD,
        "available_seats": 0,     # 기본값: 타겟 버스가 화면에 없으면 0으로 간주
        "meets_threshold": False,
        "url": URL,
        "note": "",
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            context = browser.new_context(
                locale="ko-KR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 2000},
            )
            page = context.new_page()

            page.goto(URL, wait_until="domcontentloaded", timeout=60000)

            # JS 렌더링 대기 (networkidle이 안 떨어질 수도 있어 예외 허용)
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except PWTimeoutError:
                pass

            # 목록이 로딩될 때까지 대기(없으면 0으로 간주하고 종료)
            try:
                page.wait_for_selector("span.bin-ttl-box-number.bin-name", timeout=30000)
            except PWTimeoutError:
                result["note"] = "목록 셀렉터가 시간 내 로딩되지 않아 0으로 간주함."
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            # 타겟 버스(0106편) 요소 탐색: 없으면 정상 케이스(좌석 0)로 처리
            bus = page.locator("span.bin-ttl-box-number.bin-name", has_text=TARGET_LABEL)

            if bus.count() == 0:
                result["note"] = "0106편이 목록에 없음(공석/판매표시 없음으로 간주) -> 0"
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            bus_first = bus.first

            # 0106편이 포함된 가장 가까운 상위 컨테이너에서 vacancy-num을 찾음
            container = bus_first.locator(
                "xpath=ancestor::*[.//span[contains(@class,'vacancy-num')]][1]"
            )

            if container.count() == 0:
                result["note"] = "0106편 컨테이너에서 vacancy-num을 찾지 못해 0으로 간주함."
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            vac = container.locator("span.vacancy-num").first
            if vac.count() == 0:
                result["note"] = "span.vacancy-num이 없어 0으로 간주함."
                print(json.dumps(result, ensure_ascii=False))
                browser.close()
                return 0

            vac_text = vac.inner_text().strip()
            seats = to_int_safe(vac_text)

            if seats is None:
                result["note"] = f"vacancy-num 파싱 실패('{vac_text}') -> 0으로 간주함."
                seats = 0

            result["available_seats"] = seats
            result["meets_threshold"] = seats >= THRESHOLD

            browser.close()

    except Exception as e:
        # 접속 실패/차단 등 '진짜 오류'만 ok=false로 처리하여 워크플로우가 실패하도록 함
        result["ok"] = False
        result["note"] = f"렌더링/파싱 실패: {type(e).__name__}: {e}"

    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())

