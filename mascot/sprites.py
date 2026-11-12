"""날개 모양과 바닥에 떨어지는 열매(Item)"""

import math
import time
import tkinter as tk

from .constants import KEY, TICK_MS


# 그림 모드의 왼쪽 날개 모양 (어깨 기준 좌표, 그림 높이 110px 기준).
# 위쪽 바깥으로 뻗고, 바깥 끝은 깃털 세 갈래, 몸 쪽 아래에는 초록 깃털.
# 부드러운 곡선(smooth)으로 그려서 깃털 끝은 둥글고, 같은 점을 두 번 적은 홈만 또렷하게 들어감.
# x>0 쪽은 몸 위에 겹치는 날개 뿌리(둥글게 마무리).
WING_SHAPE = [
    (6, -14), (-6, -30), (-22, -43),
    (-38, -50), (-46, -44),            # 맨 끝 깃털 (둥근 끝)
    (-38, -34), (-38, -34),            # 홈
    (-48, -30), (-48, -21),            # 두 번째 깃털
    (-37, -17), (-37, -17),            # 홈
    (-44, -10), (-38, -2),             # 세 번째 깃털
    (-22, 2), (-8, 7), (2, 9),
    (8, 5), (9, -3), (7, -10),         # 몸 위로 살짝 올라오는 둥근 뿌리
]
WING_GREEN = [
    (5, -3), (-6, -10), (-16, -12),
    (-22, -9),                         # 첫 번째 초록 깃털
    (-17, -5), (-17, -5),              # 홈
    (-25, -1), (-21, 4),               # 두 번째 초록 깃털
    (-13, 4), (-13, 4),                # 홈
    (-13, 8), (-5, 9),                 # 세 번째 초록 깃털
    (2, 8), (6, 4),
]
# 테두리를 그릴 점 구간 (몸 밖으로 나온 부분만). 그 밖의 뿌리 쪽은 테두리 없음.
WING_SHAPE_EDGE = (1, 14)
WING_GREEN_EDGE = (1, 11)
# 날개 자세별로 펼친 각도 (도). 'up' 은 위로 활짝, 'mid' 는 옆으로 반쯤
WING_ANGLES = {"up": 0, "mid": -38}
WING_SHOULDER = 5  # 어깨가 몸 가장자리에서 안쪽으로 들어간 거리 (그림 높이 110px 기준)


def wing_reach():
    """날개 끝이 몸 가장자리에서 옆으로 가장 멀리 나가는 거리 (그림 높이 110px 기준).
    어느 자세에서든 잘리지 않게 창 옆 여백을 정할 때 씀"""
    far = 0.0
    for deg in WING_ANGLES.values():
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)
        for shape in (WING_SHAPE, WING_GREEN):
            for px, py in shape:
                far = max(far, -(px * ca - py * sa) - WING_SHOULDER)
    return far


class Item:
    """밥그릇(또는 바닥)에 떨어지는 열매. 마우스로 집어 던질 수 있음."""

    def __init__(self, pet, x, y, rest_y=None):
        self.pet = pet
        self.size = int(20 * pet.S)
        self.x, self.y, self.vx, self.vy = x, y, 0.0, 0.0
        self.rest_y = rest_y  # 바닥 대신 멈출 높이(아랫면). 밥그릇에 떨어뜨린 열매면 밥그릇 안쪽 높이
        self.in_bowl = rest_y is not None
        self.dragging = False

        w = self.win = tk.Toplevel(pet.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", KEY)
        w.configure(bg=KEY)
        self.c = tk.Canvas(w, width=self.size, height=self.size, bg=KEY, highlightthickness=0, bd=0)
        self.c.pack()
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_motion)
        self.c.bind("<ButtonRelease-1>", self.on_release)
        self.draw()
        self.place()

    def ground(self):
        return (self.rest_y if self.rest_y is not None else self.pet.floor_at(self.x + self.size / 2)) - self.size

    def near_ground(self):
        return not self.dragging and self.y >= self.ground() - 30 * self.pet.S

    def draw(self):
        c, s = self.c, self.size
        c.delete("all")
        m = max(1, s // 12)
        c.create_oval(m, m * 3, s - m, s - m, fill="#3f7fd8", outline="#1f3f78", width=max(1, m // 2 + 1))
        c.create_oval(s * 0.3, s * 0.35, s * 0.45, s * 0.5, fill="#9cc4ff", outline="")
        c.create_polygon(s * 0.5, m * 3.5, s * 0.75, 0, s * 0.85, m * 2, smooth=True,
                         fill="#58b84f", outline="#2f7d32")

    def place(self):
        self.win.geometry(f"+{int(self.x)}+{int(self.y)}")

    def update(self):
        if self.dragging or (self.vx == self.vy == 0 and self.y >= self.ground()):
            return  # 집고 있거나 멈춰 있으면 창을 옮길 필요 없음
        S, p = self.pet.S, self.pet
        self.vy += 0.8 * S
        self.x += self.vx
        self.y += self.vy
        if self.x < p.left or self.x > p.right - self.size:
            self.x = min(max(self.x, p.left), p.right - self.size)
            self.vx = -self.vx * 0.6
        if self.y >= self.ground():
            self.y = self.ground()
            self.vx = self.vy = 0
        self.place()

    def remove(self):
        if self in self.pet.items:
            self.pet.items.remove(self)
        self.win.destroy()

    def on_press(self, e):
        self.dragging = True
        self.grab = (e.x_root - self.x, e.y_root - self.y)
        self.trail = [(time.time(), self.x, self.y)]

    def on_motion(self, e):
        self.x = e.x_root - self.grab[0]
        self.y = e.y_root - self.grab[1]
        now = time.time()
        self.trail.append((now, self.x, self.y))
        self.trail = [p for p in self.trail if now - p[0] < 0.1] or self.trail[-1:]
        self.place()

    def on_release(self, e):
        self.dragging = False
        self.rest_y, self.in_bowl = None, False  # 밥그릇에서 꺼내 던지면 바닥으로 떨어짐
        t0, x0, y0 = self.trail[0]
        t1, x1, y1 = self.trail[-1]
        dt = max(t1 - t0, 0.016)
        lim = 35 * self.pet.S
        self.vx = max(-lim, min(lim, (x1 - x0) / dt * TICK_MS / 1000))
        self.vy = max(-lim, min(lim, (y1 - y0) / dt * TICK_MS / 1000))
