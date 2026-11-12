"""공휴일(ICS) 내려받기와 휴일 날짜 계산"""

import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from .constants import HOLIDAY_ICS


def ics_days(text, accept):
    """iCal(.ics) 일정 중 accept(제목, 설명) 이 참인 일정이 걸친 날짜들 {'YYYY-MM-DD'}"""
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]  # 긴 줄은 다음 줄에 이어서 적혀 있음
        else:
            lines.append(raw)
    days, ev = set(), None
    for line in lines:
        if line == "BEGIN:VEVENT":
            ev = {}
        elif line == "END:VEVENT" and ev is not None:
            start, end = ev.get("DTSTART", ""), ev.get("DTEND", "")
            if len(start) >= 8 and accept(ev.get("SUMMARY", ""), ev.get("DESCRIPTION", "")):
                d0 = datetime.strptime(start[:8], "%Y%m%d").date()
                d1 = datetime.strptime(end[:8], "%Y%m%d").date() if len(end) >= 8 else d0
                if len(start) == 8 and len(end) == 8:
                    d1 = max(d0, d1 - timedelta(days=1))  # 하루 종일 일정의 끝 날짜는 '다음 날'로 적혀 있음
                d = d0
                while d <= d1 and (d1 - d0).days < 400:
                    days.add(d.isoformat())
                    d += timedelta(days=1)
            ev = None
        elif ev is not None and ":" in line:
            key, value = line.split(":", 1)
            ev[key.split(";")[0]] = value.replace("\\n", "\n").replace("\\,", ",")
    return days


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Namolppaemi"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "replace")


class HolidayFetcher(threading.Thread):
    """공휴일 목록을 받아서 out 큐로 넘김 (실패하면 None)"""

    def __init__(self, out):
        super().__init__(daemon=True)
        self.out = out

    def run(self):
        try:
            self.out.put(ics_days(fetch_text(HOLIDAY_ICS), lambda s, d: d.startswith("공휴일")))
        except Exception:
            self.out.put(None)
