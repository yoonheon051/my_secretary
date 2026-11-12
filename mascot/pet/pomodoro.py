"""재우기(뽀모도로) 타이머"""

from datetime import date, datetime

from ..constants import (
    BREAK_MIN,
    BREAK_RESET_MIN,
    FOCUS_MIN,
    MORNING_UNTIL,
    UNIT,
    WORK_STRETCH_MIN,
)
from ..winapi import idle_seconds


class PomodoroMixin:
    # ---------- 타이머 ----------
    def check_timers(self, now):
        if self.pomo_phase and now >= self.pomo_end:
            if self.pomo_phase == "focus":
                today = date.today().isoformat()
                if self.pomo_day != today:
                    self.pomo_day, self.pomo_count = today, 0
                self.pomo_count += 1
                self.gain(mood=10, affection=2)
                self.pomo_phase = "break"
                self.pomo_end = now + BREAK_MIN * UNIT
                self.say(f"푹 잤다! {FOCUS_MIN}분 집중 끝 ({self.pomo_count}번째)\n{BREAK_MIN}분 쉬어요. 기지개 한번 켜볼까요?", 10)
                # 볼에서 나오는 건 update_ball 이 함 (재우기가 끝났으니 볼 안에 있을 이유가 없어짐)
            else:
                self.pomo_phase = None
                self.say("쉬는 시간 끝!\n또 집중하려면 우클릭 → 재우기", 10)
        self.check_activity(now)

    def check_activity(self, now):
        """똑똑한 휴식 알림: 쉬지 않고 WORK_STRETCH_MIN 분 넘게 마우스·키보드를 썼을 때만 스트레칭 알림.
        입력이 BREAK_RESET_MIN 분 없으면 쉰 것으로 보고 처음부터 다시 셈"""
        if now - self.last_activity_check < 5:
            return
        self.last_activity_check = now
        if idle_seconds() >= BREAK_RESET_MIN * 60:
            self.active_since = None
        elif self.active_since is None:
            self.active_since = now
        elif (self.stretch_var.get() and self.pomo_phase != "focus"
              and now - self.active_since >= WORK_STRETCH_MIN * 60):
            self.active_since = now  # 알린 뒤 다시 셈
            self.say(f"{WORK_STRETCH_MIN}분 넘게 쉬지 않고 일했어요.\n잠깐 일어나서 어깨 돌리고 물 한 잔 마셔요.", 10)
            if self.state in ("idle", "walk", "sleep", "home"):
                self.set_state("happy", 1.2)

    def check_morning(self, now):
        """출근 인사: MORNING_UNTIL 시 전에 그날 처음 자리에 앉으면 오늘 일정·할 일을 한 번 알려 줌"""
        if now - self.last_morning_check < 5:
            return
        self.last_morning_check = now
        t = datetime.now()
        today = t.date().isoformat()
        if (self.greet_day == today or t.hour >= MORNING_UNTIL or not self.has_schedule_source
                or self.brief or idle_seconds() > 30):  # 브리핑 알림이 떠 있으면 그걸 가리지 않게 나중에
            return
        self.greet_day = today
        self.save_pet()
        self.gcal_run("morning", self.gather_today)
