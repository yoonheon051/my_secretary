"""집·놀러 가기·열린 창 위에 서기"""

import random
import time

from ..constants import HOME_RANGE, VISIT_OTHER, WANDER_CHANCE
from ..winapi import find_platforms, user32


class RoamingMixin:
    # ---------- 집 / 놀러 간 곳 ----------
    def anchor(self):
        """지금 머무를 곳 (발판, 기준 x). 잠깐 놀러 간 곳이 있으면 그곳, 아니면 바닥의 몬스터볼 (발판 없음 = 바닥)"""
        v = self.visit
        if v and time.time() < v["until"] and (v["surface"] is None or self.surf_rect(v["surface"])):
            return v["surface"], v["dx"]
        self.visit = None
        return None, self.ball_cx

    @property
    def home_surface(self):
        return self.anchor()[0]

    def home_cx(self):
        """머무를 곳 중심의 화면 x"""
        surf, dx = self.anchor()
        return dx if surf is None else self.surf_rect(surf)[0] + dx

    def home_y(self):
        rect = self.surf_rect(self.home_surface)
        return rect[1] if rect else self.floor_at(self.home_cx())  # 바닥이면 그 자리 모니터의 바닥

    def home_range(self):
        self.anchor()  # 놀러 간 곳이 끝났으면 정리
        return (HOME_RANGE if self.visit else 6) * self.S  # 볼 집은 둥지라서 거의 안 움직임

    def start_visit(self, secs_range):
        """지금 있는 곳 주변에 잠시 머물기 (볼 근처면 그냥 집)"""
        cx = self.x + self.W / 2
        if self.surface is None and self.monitor_at(cx) == self.home_area and abs(cx - self.ball_cx) < 140 * self.S:
            self.visit = None
            return
        rect = self.surf_rect(self.surface)
        self.visit = {"surface": self.surface if rect else None,
                      "dx": cx - rect[0] if rect else cx,
                      "until": time.time() + random.uniform(*secs_range)}

    def at_home(self):
        return (self.surface == self.home_surface
                and abs(self.x + self.W / 2 - self.home_cx()) <= self.home_range() + 2)

    def go_home(self):
        if self.home_surface is None and self.surface is not None:
            # 집은 바닥인데 창 위에 있으면 파닥이며 집으로 날아 내려감
            self.left_surface = self.surface
            self.fall_down()
        elif self.home_surface is not None and self.surface != self.home_surface:
            self.start_fly()  # 집인 창으로 날아감
        elif self.far_from_home():
            self.start_fly()  # 멀리 있으면 걸어가지 않고 바로 날아서 돌아감
        else:
            self.set_state("home")

    def far_from_home(self):
        """집이 다른 모니터에 있거나 걸어가기엔 먼지 (이럴 땐 걷지 않고 날아서 돌아감)"""
        cx, hx = self.x + self.W / 2, self.home_cx()
        return abs(hx - cx) > 400 * self.S or self.monitor_at(cx) != self.monitor_at(hx)

    def choose_next(self):
        if self.ball_wanted():  # 재우기 중 등: 볼 안에 있거나 볼로 가는 중
            self.set_state("focus" if self.in_ball else "toball")
            return
        if not self.roam_var.get():
            if not self.at_home():
                self.go_home()
                return
            r = random.random()  # 집에서는 차분하게
            if (self.on_home_floor() and len(self.monitors) > 1 and self.wander_var.get()
                    and random.random() < WANDER_CHANCE):
                self.visit_other_monitor()  # 가끔 다른 모니터로 놀러 감
            elif r < 0.70 or self.claude_busy:  # 둥지(볼) 안에서는 걸어 다니지 않고 가만히. Claude 가 일하는 동안엔 안 자고 같이 고민
                self.set_state("idle", random.uniform(3, 7))
            else:
                self.set_state("sleep", random.uniform(8, 20))
            return
        r = random.random()
        if r < 0.45:
            if random.random() < 0.4:
                self.dir = -self.dir
            self.set_state("walk", random.uniform(3, 8))
        elif r < 0.70:
            self.set_state("idle", random.uniform(2, 5))
        elif r < 0.85:
            self.set_state("sleep", random.uniform(6, 14))
        else:
            self.start_fly()

    def visit_other_monitor(self, announce=False):
        """다른 모니터 바닥으로 날아가서 VISIT_OTHER 초 동안 그 근처에서 놀다가 볼로 돌아옴"""
        here = self.monitor_at(self.x + self.W / 2)
        others = [m for m in self.monitors if m != here]
        if not others:
            if announce:
                self.say("모니터가 하나뿐이에요.", 3)
            return
        l, t, r, b = random.choice(others)
        cx = l + (r - l) * random.uniform(0.25, 0.75)
        self.visit = {"surface": None, "dx": cx, "until": time.time() + random.uniform(*VISIT_OTHER)}
        if announce:
            self.say("저쪽 모니터 구경 갈래요!", 2)
        self.start_fly()

    def fly_home(self):
        """메뉴 '집으로 돌아가기': 어디에 있든 (다른 모니터·앱 창 위·공중·자유롭게 돌아다니는 중에도)
        날아서 바닥의 몬스터볼 집으로 돌아가 내려앉음"""
        if self.state in ("drag", "flutter"):  # 집어 든 중이거나 이미 날아서 집으로 가는 중
            return
        self.visit = None  # 놀러 간 곳이 있으면 취소. 안 그러면 놀러 간 곳을 '집'으로 봄
        if self.at_home() and self.state not in ("fall", "hover", "fly", "glide"):
            self.say("이미 집에 있어요!", 2)
            return
        self.say("집으로 갈래요!", 2)
        self.fly_to(self.home_cx(), self.home_y())

    def fly_to(self, x, y):
        """가운데 x, 발이 닿을 높이 y 로 날아가서 내려앉음 (어디에 있든)"""
        S = self.S
        self.surface = self.left_surface = None
        self.thrown = False
        self.refresh_platforms()
        self.dir = 1 if x > self.x + self.W / 2 else -1
        self.fly_plat = (x, y)
        self.fly_target = max(self.top + 10 * S, min(self.y, y - self.foot) - random.uniform(80, 160) * S)
        self.set_state("fly")

    def start_fly(self):
        if self.state in ("drag", "fall", "flutter", "hover", "fly", "glide"):
            return
        S = self.S
        self.surface = None
        self.dir = random.choice((-1, 1))
        self.fly_plat = None
        self.refresh_platforms()  # 날아가 앉을 창을 고르려고 지금 창 목록을 읽음
        roomy = [p for p in self.platforms if p[2] - p[1] >= 100 * S]
        if not self.roam_var.get():
            # 집 모드: 살짝 날아올랐다가 집으로 돌아와 내려앉기
            hy = self.home_y()
            self.fly_plat = (self.home_cx(), hy)
            self.fly_target = max(self.top + 10 * S, min(self.y, hy - self.foot) - random.uniform(80, 160) * S)
        elif roomy and random.random() < 0.6:
            # 열린 창 중 하나를 골라 그 위로 날아가 내려앉기
            _, l, r, y = random.choice(roomy)
            self.fly_plat = ((l + r) / 2, y)
            self.fly_target = max(self.top + 10 * S, y - self.foot - 60 * S)
        else:
            self.fly_target = max(self.top + 20 * S, self.y - random.uniform(150, 350) * S)
        self.set_state("fly")

    # ---------- 창 위에 서기 ----------
    def refresh_platforms(self):
        self.last_platforms = time.time()
        self.platforms = []
        if user32 is None or not self.perch_var.get():
            return
        try:
            self.platforms += find_platforms((self.left, self.vtop, self.right, self.vbottom))  # 모든 모니터
        except Exception:
            pass

    def landing(self, prev_feet):
        """이번 틱에 발이 지나간 창 윗변 중 가장 위의 것"""
        cx, feet = self.x + self.W / 2, self.y + self.foot
        best = None
        for p in self.platforms:
            if p[0] == self.left_surface:  # 방금 일부러 뛰어내린 창
                continue
            # 집 모드에서는 사용자가 던졌을 때, 머무를 창으로 돌아갈 때만 창 위에 내려앉음
            if not (self.roam_var.get() or self.thrown or p[0] == self.home_surface):
                continue
            _, l, r, y = p
            if l <= cx <= r and prev_feet <= y + 1 and feet >= y and (best is None or y < best[3]):
                best = p
        return best

    def stand_on(self, hwnd):
        rect = self.surf_rect(hwnd)
        self.surface = hwnd if rect else None
        self.surf_left = rect[0] if rect else 0
        self.leap_ok = False
        self.left_surface = None

    def drop(self):
        self.left_surface = self.surface
        self.surface = None
        self.vx, self.vy = self.dir * 1.5 * self.S, -3 * self.S
        self.set_state("fall")

    def fall_down(self):
        """발밑이 사라졌을 때: 집 모드면 날개를 파닥이며 집으로 날아가고, 자유 모드면 그냥 떨어짐"""
        if self.surface is not None:
            self.left_surface = self.surface  # 방금 있던 발판에 바로 다시 내려앉지 않게
        self.surface = None
        self.vx = self.vy = 0
        self.set_state("fall" if self.roam_var.get() else "flutter")

    def follow_surface(self, ground):
        """발밑(바닥 또는 창)을 따라 위치를 맞춤. 발밑이 사라지면 떨어지기 시작하고 False."""
        if self.surface is None:
            if self.y < ground - 1:
                self.fall_down()
                return False
            self.y = ground
            return True
        rect = self.surf_rect(self.surface)
        if rect is not None:
            l, t, r, b = rect
            self.x += l - self.surf_left  # 창을 옮기면 같이 이동
            self.surf_left = l
            cx = self.x + self.W / 2
            if l <= cx <= r and self.top + 60 <= t <= self.bottom - 20:
                self.y = t - self.foot
                return True
        self.fall_down()
        return False

    def avoid_window_edge(self, step):
        """창 위를 걷다가 끝에 오면 대부분 돌아서고, 가끔은 그냥 뛰어내림"""
        if self.surface is None or self.leap_ok:
            return
        rect = self.surf_rect(self.surface)
        if rect is None:
            return
        ncx = self.x + self.W / 2 + self.dir * step
        margin = 15 * self.S
        if not (rect[0] + margin <= ncx <= rect[2] - margin):
            if self.roam_var.get() and random.random() < 0.25:
                self.leap_ok = True
            else:
                self.dir = -self.dir

    def turn_at_edges(self):
        if self.x < self.left:
            self.x, self.dir = self.left, 1
        elif self.x > self.right - self.W:
            self.x, self.dir = self.right - self.W, -1
