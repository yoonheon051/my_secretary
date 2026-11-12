"""모니터·바닥 높이·상태 바꾸기"""

import time

from ..winapi import monitor_areas


class ScreenMixin:
    # ---------- 화면 / 상태 ----------
    def update_area(self):
        """모니터들의 작업 영역을 읽음.
        self.left/right: 모든 모니터를 합친 가로 범위 (여기까지 돌아다닐 수 있음)
        self.top/bottom, self.mon_left/mon_right: 지금 나몰빼미가 있는 모니터 (pick_monitor 가 매 틱 맞춤)
        self.home_area: 주 모니터 (둥지 집이 있는 곳)"""
        mons = monitor_areas() or [(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight(), True)]
        self.monitors = [m[:4] for m in mons]
        self.home_area = next((m[:4] for m in mons if m[4]), self.monitors[0])
        self.left = min(m[0] for m in self.monitors)
        self.right = max(m[2] for m in self.monitors)
        self.vtop = min(m[1] for m in self.monitors)
        self.vbottom = max(m[3] for m in self.monitors)
        self.pick_monitor()

    def monitor_at(self, x):
        """가로 위치 x 가 들어 있는 모니터 영역 (사이에 빈틈이면 가장 가까운 모니터)"""
        return min(self.monitors, key=lambda m: 0 if m[0] <= x < m[2] else min(abs(x - m[0]), abs(x - m[2])))

    def floor_at(self, x):
        """가로 위치 x 의 바닥 높이 (그 모니터의 작업 표시줄 위)"""
        return self.monitor_at(x)[3]

    def pick_monitor(self):
        cx = self.x + self.W / 2 if hasattr(self, "x") else (self.home_area[0] + self.home_area[2]) / 2
        self.mon_left, self.top, self.mon_right, self.bottom = self.monitor_at(cx)

    def blocked_ahead(self, step):
        """걸어서 한 걸음 가면 바닥이 더 높은 모니터로 넘어가는지 (걸어서는 못 올라가니 돌아섬)"""
        if self.surface is not None:
            return False
        nx = self.x + self.W / 2 + self.dir * step
        return self.floor_at(nx) < self.bottom - 2

    def ground(self):
        return self.bottom - self.foot

    def set_state(self, name, secs=None):
        self.state = name
        self.until = time.time() + secs if secs else 0
