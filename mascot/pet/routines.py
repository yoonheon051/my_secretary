"""퇴근길 날씨·정해진 시간의 신나는 포즈"""

import queue
from datetime import date, datetime

from ..constants import DAILY_CHEERS, RAIN_CHECK_MIN, UMBRELLA_MIN, WEATHER_SAY_HOUR
from ..weather import RainWatcher, WeatherFetcher


class RoutinesMixin:
    # ---------- 퇴근길 날씨 ----------
    def fetch_weather(self, scheduled=False):
        if not self.weather_busy:
            self.weather_busy = True
            WeatherFetcher(self.weather_q, scheduled).start()

    def update_rain(self, now):
        """지금 비가 오면 우산을 계속 듦 (자는 중에도). 확인할 때마다 우산 시간을 연장"""
        if now >= self.rain_check_at and not self.rain_busy:
            self.rain_busy = True
            self.rain_check_at = now + RAIN_CHECK_MIN * 60
            RainWatcher(self.rain_q).start()
        try:
            raining, err = self.rain_q.get_nowait()
        except queue.Empty:
            return
        self.rain_busy = False
        if err is not None:
            self.rain_check_at = now + 120  # 실패하면 2분 뒤 다시
        elif raining:
            self.umbrella_until = max(self.umbrella_until, now + (RAIN_CHECK_MIN + 2) * 60)

    def update_weather(self, now):
        self.update_rain(now)
        if self.crossed(30):
            t = datetime.now()
            today = t.date().isoformat()
            if (t.hour == WEATHER_SAY_HOUR and self.weather_said != today and now >= self.weather_retry_at
                    and not self.is_day_off(t.date())):
                self.fetch_weather(scheduled=True)
        try:
            result, err, scheduled = self.weather_q.get_nowait()
        except queue.Empty:
            return
        self.weather_busy = False
        if err is not None:
            if scheduled:
                self.weather_retry_at = now + 300  # 5분 뒤 다시 시도
            else:
                self.say("날씨를 받아오지 못했어요.\n인터넷 연결을 확인해 주세요.", 4)
            return
        msg, rain = result
        if scheduled:
            self.weather_said = date.today().isoformat()
            self.save_pet()
        self.say(msg, 12)
        if rain:
            self.umbrella_until = now + UMBRELLA_MIN * 60
        if self.state in ("idle", "walk", "sleep"):
            self.set_state("idle", 3)  # 자고 있었으면 깨서 말함

    # ---------- 매일 정해진 시간의 신나는 포즈 (점심·퇴근) ----------
    def current_cheer(self):
        """지금이 DAILY_CHEERS 시간대면 (말, 끝나는 시각), 아니면 None"""
        now = datetime.now()
        hm = f"{now:%H:%M}"
        for start, end, text in DAILY_CHEERS:
            if start <= hm < end:
                h, m = map(int, end.split(":"))
                return text, now.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
        return None

    def update_cheer(self, now):
        if not self.crossed(15):
            return
        cheer = self.current_cheer()
        if cheer is None:
            if self.cheering:
                if self.state == "happy":
                    self.set_state("idle", 2)  # 시간이 끝나면 평소처럼
                if self.bubble_until and self.blabel.cget("text") == self.cheering:
                    self.hide_bubble()
            self.cheering = None
            return
        text, end = cheer
        if self.pomo_phase == "focus":
            return  # 재우기 중에는 깨우지 않음
        self.cheering = text
        if self.state in ("idle", "walk", "sleep", "home", "happy", "land") and not self.target_item():
            self.set_state("happy", 2)  # 계속 연장해서 시간대 내내 신나는 포즈 (열매·공이 있으면 그쪽 먼저)
        if not self.bubble_until:  # 다른 말풍선이 없을 때만 (메일 알림 등이 끝나면 다시 띄움)
            self.say(text, max(1, end - now))
