"""그리기"""

import math
import os
import random
import time
from datetime import datetime

from ..constants import (
    BROWN,
    CREAM,
    EYE,
    FOOT,
    GRUMPY_AT,
    HERE,
    HUNGRY_AT,
    KEY,
    LEAF,
    POSE_INFO,
)
from ..sprites import (
    WING_ANGLES,
    WING_GREEN,
    WING_GREEN_EDGE,
    WING_SHAPE,
    WING_SHAPE_EDGE,
    WING_SHOULDER,
)
from ..ui import UI_TEXT


class DrawingMixin:
    # ---------- 그리기 ----------
    def draw(self, now):
        """나몰빼미 그리기. 모습이 지난번과 똑같으면 다시 그리지 않고 False (CPU 절약)"""
        c, S, st, f = self.canvas, self.S, self.state, self.frame

        self.bob, wings, eyes, zz = 0.0, "down", "open", False
        if random.random() < 0.012 * self.step:  # 가끔 눈 깜빡 (틱이 느릴 땐 그만큼 확률을 키움)
            self.blink_until = now + 0.15

        if st in ("walk", "goto", "home", "toball"):
            self.bob = -abs(math.sin(f * 0.45)) * 4
        elif st == "eat":
            eyes = "closed"
            self.bob = abs(math.sin(f * 0.6)) * 2.5
        elif st == "happy":
            # 신나는 포즈: 날개를 위로 활짝, 웃는 눈(^ ^), 볼터치, 반짝이는 별 (draw_sparkles)
            eyes = "happy"
            self.bob = -abs(math.sin(f * 0.3)) * 8
            wings = "up" if (f // 4) % 3 else "mid"
        elif st == "pet":  # 쓰다듬어 주는 중: 웃는 눈, 손에 눌려 살짝 꾹꾹 (draw_hand)
            eyes = "happy"
            self.bob = abs(math.sin(f * 0.22)) * 1.5
        elif st == "sleep":
            eyes, zz = "closed", True
            self.bob = math.sin(f * 0.08) * 1.2
        elif st in ("fly", "glide", "flutter", "hover"):
            wings = "up" if (f // (6 if st == "glide" else 3)) % 2 else "mid"
        elif st == "fall":
            wings, eyes = "up", "wide"
        elif st == "drag":
            wings = "up" if (f // 4) % 2 else "mid"
            eyes = "wide"
        elif st == "land":
            self.bob = 3
            eyes = "dizzy" if self.dizzy else "closed"
        elif st == "focus":  # 재우기(뽀모도로) 중: 자는 모습 그대로
            eyes, zz = "closed", True
            self.bob = math.sin(f * 0.08) * 1.2
        if eyes == "open" and now < self.blink_until:
            eyes = "closed"

        # 화면에 보이는 모습을 결정하는 값들. 지난번과 같으면 그대로 둠
        self.win_bob = round(self.bob * S)  # 창 위치로 반영 (tick)
        sig = (wings, eyes, zz and (f // 15) % 3, self.dir,
               self.has_letter, bool(self.brief), now < self.umbrella_until, self.mood_pose(wings),
               f // 2 if st in ("happy", "pet") else 0,              # 반짝이는 별, 쓰다듬는 손
               (f // 9) % 4 if self.claude_busy else -1,             # 고민 구름의 점
               int(now * 30) if now < self.heart_until else 0,       # 떠오르는 하트
               int(self.travel * 30) if st in ("capture", "release") else -1)  # 볼로 빨려 들어가는 모습
        if sig == self.last_sig:
            return False
        self.last_sig = sig
        c.delete("all")
        if st in ("capture", "release"):
            self.draw_travel()
        else:
            self.draw_image(wings, eyes, zz)
        return True

    def draw_sparkles(self):
        """신날 때 머리 주위에서 반짝이는 노란 별 두 개"""
        if self.state != "happy":
            return
        c, S, f = self.canvas, self.S, self.frame
        lw = max(1, round(1.5 * S))
        top = self.head
        side = 1 if self.dir > 0 else -1
        stars = ((self.W / 2 - side * 50 * S, top + 6 * S, 10, 0.0),   # 큰 별 (머리 옆, 바라보는 반대쪽)
                 (self.W / 2 + side * 44 * S, top - 4 * S, 6, 1.6))    # 작은 별 (머리 반대편 위)
        for cx, cy, size, phase in stars:
            r = size * S * (0.8 + 0.25 * math.sin(f * 0.35 + phase))  # 반짝반짝 커졌다 작아짐
            pts = []
            for k in range(10):
                a = math.radians(-90 + k * 36)
                rr = r if k % 2 == 0 else r * 0.45
                pts += [cx + rr * math.cos(a), cy + rr * math.sin(a)]
            c.create_polygon(*pts, fill="#ffe45c", outline="#ff8fb8", width=lw, joinstyle="round")

    def draw_hand(self):
        """놀아주기: 위에서 내려온 손이 머리를 좌우로 쓰다듬음 (손가락이 머리 위에 살짝 걸침)"""
        if self.state != "pet":
            return
        c, S, f = self.canvas, self.S, self.frame
        lw = max(1, round(1.5 * S))
        skin, skin_d = "#ffe0c4", "#9a5a34"
        cx = self.W / 2 + math.sin(f * 0.22) * 16 * S
        hy = self.head + 12 * S  # 손가락 끝 높이
        c.create_rectangle(cx - 10 * S, hy - 32 * S, cx + 10 * S, hy - 23 * S,
                           fill="#8fbbe8", outline="#5f8fc0", width=lw)  # 소매
        for i, dx in enumerate((-9, -3, 3, 9)):
            tip = 3 if i in (1, 2) else 1  # 가운데 손가락이 조금 더 김
            c.create_oval(cx + (dx - 3.2) * S, hy - 12 * S, cx + (dx + 3.2) * S, hy + tip * S,
                          fill=skin, outline=skin_d, width=lw)
        side = 1 if self.dir > 0 else -1  # 엄지는 바라보는 쪽
        c.create_oval(cx + side * 10 * S - 4 * S, hy - 21 * S, cx + side * 10 * S + 4 * S, hy - 8 * S,
                      fill=skin, outline=skin_d, width=lw)
        c.create_oval(cx - 13 * S, hy - 25 * S, cx + 13 * S, hy - 6 * S, fill=skin, outline=skin_d, width=lw)

    def draw_thinking(self):
        """Claude 가 작업 중일 때: 머리 옆에 생각 구름, 안의 점 세 개가 차례로 진해짐"""
        if not self.claude_busy or self.state in ("capture", "release"):
            return
        c, S = self.canvas, self.S
        side = -1 if self.dir > 0 else 1  # 바라보는 반대쪽 머리 위
        hx, top = self.W / 2, self.head
        edge, fill, dot_on, dot_off = "#5b6b5d", "#ffffff", UI_TEXT, "#b9c2b6"
        # 머리에서 구름으로 이어지는 작은 동그라미 두 개
        for dx, dy, r in ((16, 4, 2.2), (23, -2, 3.2)):
            x, y = hx + side * dx * S, top + dy * S
            c.create_oval(x - r * S, y - r * S, x + r * S, y + r * S, fill=fill, outline=edge,
                          width=max(1, round(S)))
        # 구름: 테두리용으로 조금 크게 한 번, 채우기로 한 번 (겹친 안쪽 선이 안 보이게)
        cx, cy = hx + side * 40 * S, top - 7 * S  # 캔버스 위쪽 여백 안에 들어오는 높이
        blobs = ((-9, 1, 8), (0, -2, 9), (9, 1, 8), (0, 4, 7))
        for dx, dy, r in blobs:
            rr = (r + 1.2) * S
            c.create_oval(cx + dx * S - rr, cy + dy * S - rr, cx + dx * S + rr, cy + dy * S + rr,
                          fill=edge, outline="")
        for dx, dy, r in blobs:
            rr = r * S
            c.create_oval(cx + dx * S - rr, cy + dy * S - rr, cx + dx * S + rr, cy + dy * S + rr,
                          fill=fill, outline="")
        phase = (self.frame // 9) % 4  # 0~2: 점 하나씩, 3: 셋 다
        for i, dx in enumerate((-7, 0, 7)):
            on = phase == 3 or phase == i
            r = (2.1 if on else 1.7) * S
            c.create_oval(cx + dx * S - r, cy + 1 * S - r, cx + dx * S + r, cy + 1 * S + r,
                          fill=dot_on if on else dot_off, outline="")

    def draw_hearts(self, now):
        if now >= self.heart_until:
            return
        S = self.S
        t = 1 - (self.heart_until - now) / 1.2  # 0 → 1
        y = self.head + 4 * S - t * 16 * S
        for i, dx in enumerate((-14, 16)):
            self.draw_heart(self.W / 2 + dx * S, y - i * 5 * S, (5 + i * 1.5) * S)

    # 글자(z, ♥)는 가장자리가 투명 처리 색과 섞여 분홍 테두리가 생겨서, 선과 도형으로 직접 그림
    def draw_z(self, cx, cy, size, color, canvas=None):
        h = size / 2
        (canvas or self.canvas).create_line(cx - h, cy - h, cx + h, cy - h, cx - h, cy + h, cx + h, cy + h,
                                fill=color, width=max(1, round(size / 3.5)), joinstyle="miter")

    def draw_heart(self, cx, cy, size):
        r = size / 2
        c = self.canvas
        c.create_oval(cx - size, cy - r * 1.6, cx, cy + r * 0.4, fill="#ff5a7a", outline="")
        c.create_oval(cx, cy - r * 1.6, cx + size, cy + r * 0.4, fill="#ff5a7a", outline="")
        c.create_polygon(cx - size + 1, cy - r * 0.2, cx + size - 1, cy - r * 0.2, cx, cy + size * 1.1,
                         fill="#ff5a7a", outline="")

    def draw_umbrella(self, x0, y0, bw, bh, line):
        """비 예보일 때 머리 위에 드는 우산. (x0, y0, bw, bh) 는 몸통 그림이 차지하는 영역"""
        if time.time() >= self.umbrella_until:
            return
        c, S = self.canvas, self.S
        lw = max(1, round(1.5 * S))
        cx = x0 + bw * (0.88 if self.dir > 0 else 0.12)  # 바라보는 쪽 옆으로 비껴서 (눈을 안 가리게)
        r = bw * 0.5
        top = y0 - r * 0.3  # 머리 위에 살짝 걸치게 (위 여백 안에 들어오도록)
        # 손잡이: 캐노피 가운데에서 어깨까지 내려와 J 모양으로 굽음
        hy = y0 + bh * 0.62
        hook = 6 * S * (-1 if self.dir > 0 else 1)
        c.create_line(cx, top + r * 0.5, cx, hy, fill="#5a3d24", width=round(2.5 * S))
        c.create_line(cx, hy, cx, hy + 4 * S, cx + hook, hy + 6 * S, cx + hook * 1.6, hy + 2 * S,
                      smooth=True, fill="#5a3d24", width=round(2.5 * S), capstyle="round")
        # 캐노피: 반원 + 아래쪽 물결 + 살
        c.create_arc(cx - r, top, cx + r, top + r * 1.1, start=0, extent=180,
                     fill="#4caf50", outline=line, width=lw, style="pieslice")
        base = top + r * 0.55
        for i in range(4):  # 아래 가장자리 물결
            a0 = cx - r + i * r / 2
            c.create_arc(a0, base - r * 0.12, a0 + r / 2, base + r * 0.12, start=180, extent=-180,
                         fill=KEY, outline=line, width=lw, style="chord")
        for dx in (-r / 2, 0, r / 2):
            c.create_line(cx, top + 1, cx + dx, base - r * 0.1, fill="#2e7d32", width=1)
        c.create_line(cx, top - 4 * S, cx, top + 2, fill=line, width=lw)  # 꼭지

    def draw_paper(self, bx, by, line):
        """부리 끝(bx, by)에 물고 있는 오전 브리핑 신문"""
        c, S = self.canvas, self.S
        w, h = 30 * S, 20 * S
        cx, cy = bx, by + h * 0.35
        a = math.radians(-8 if self.dir < 0 else 8)
        ca, sa = math.cos(a), math.sin(a)

        def rot(pts):
            return [v for px, py in pts for v in (cx + px * ca - py * sa, cy + px * sa + py * ca)]

        lw = max(1, round(1.5 * S))
        c.create_polygon(*rot([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]),
                         fill="#fbf7ec", outline=line, width=lw)
        c.create_polygon(*rot([(-w / 2 + 3 * S, -h / 2 + 3 * S), (-w / 2 + 12 * S, -h / 2 + 3 * S),
                               (-w / 2 + 12 * S, -h / 2 + 9 * S), (-w / 2 + 3 * S, -h / 2 + 9 * S)]),
                         fill="#4caf50", outline="")  # 사진 자리
        for i, y in enumerate((-h / 2 + 4 * S, -h / 2 + 7.5 * S, -h / 2 + 12 * S, -h / 2 + 15.5 * S)):
            x0 = -w / 2 + (14 * S if i < 2 else 3 * S)
            c.create_line(*rot([(x0, y), (w / 2 - 3 * S, y)]), fill="#8a8173", width=max(1, round(S)))

    def draw_letter(self, bx, by, line):
        """부리 끝(bx, by)에 물고 있는 편지봉투"""
        c, S = self.canvas, self.S
        w, h = 24 * S, 16 * S
        cx, cy = bx, by + h * 0.3
        a = math.radians(-10 if self.dir < 0 else 10)
        ca, sa = math.cos(a), math.sin(a)

        def rot(pts):
            return [v for px, py in pts for v in (cx + px * ca - py * sa, cy + px * sa + py * ca)]

        lw = max(1, round(1.5 * S))
        c.create_polygon(*rot([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]),
                         fill="#fffdf6", outline=line, width=lw)
        c.create_line(*rot([(-w / 2, -h / 2), (0, h * 0.12), (w / 2, -h / 2)]), fill=line, width=lw)
        sx, sy = rot([(0, h * 0.12)])
        r = 2.8 * S
        c.create_oval(sx - r, sy - r, sx + r, sy + r, fill="#e53935", outline="")

    def draw_sleeping(self, ox, oy, flip, line):
        """자는 모습 (character_sleep.png) + 머리 위 z"""
        c, S = self.canvas, self.S
        iw, ih = self.iw, self.ih
        img = self.img_sleep_flip if flip else self.img_sleep
        nw, nh = img.width(), img.height()
        x0 = ox + (iw - nw) / 2          # 가운데 맞춤
        # 오려낸 자는 그림: 흰 배는 배경과 함께 지워졌으므로 그림 뒤에 타원으로 채움
        y0 = oy + ih - nh - 4 * S
        c.create_oval(x0 + nw * 0.2, y0 + nh * 0.62, x0 + nw * 0.8, y0 + nh + 5 * S,
                      fill="#ececea", outline=line, width=max(1, round(1.5 * S)))
        c.create_image(x0, y0, anchor="nw", image=img)
        bx, by = (0.38 if flip else 0.62) * nw, 0.62 * nh  # 그림 속 입 위치
        if self.brief or self.has_letter:  # 자면서도 물고 있는 신문·편지
            (self.draw_paper if self.brief else self.draw_letter)(x0 + bx, y0 + by, line)
        self.draw_sleep_z(x0 + nw * (0.82 if flip else 0.18), y0 - 2 * S, line)

    def mood_pose(self, wings="down"):
        """배고픔·기분에 따른 모습 이름 (없으면 None). 날개를 접은 평소 자세일 때만 (날기·신나기·먹기·잠은 원래 모습)"""
        if wings != "down" or self.state in ("eat", "happy", "sleep", "pet"):
            return None
        if self.full <= HUNGRY_AT and ("hungry" in self.pose_imgs or "hungry" in self.pose_overlay):
            return "hungry"
        if self.mood <= GRUMPY_AT and ("grumpy" in self.pose_imgs or "grumpy" in self.pose_overlay):
            return "grumpy"
        return None

    def draw_mood_pose(self, pose, ox, oy, flip, line):
        """배고픈 모습(눈 질끈 + 벌린 입) / 뾰로통한 모습(팔짱 + 반쯤 뜬 눈) 그림으로 그리기"""
        c, S = self.canvas, self.S
        iw, ih = self.iw, self.ih
        img = self.pose_imgs[pose][1 if flip else 0]
        info = POSE_INFO.get(pose, {})
        hw, hh = img.width(), img.height()
        x0 = ox + (iw - hw) / 2
        foot_room = 6 * S if info.get("feet") else 0
        y0 = oy + ih - hh - foot_room      # 바닥 위에 서도록 아래 맞춤
        if info.get("feet"):  # 사진에서 발이 가려져 있던 그림은 뒤에 작은 주황 발을 그림
            for fx in (0.36, 0.62):
                cx = x0 + hw * fx
                c.create_oval(cx - 6 * S, y0 + hh - 4 * S, cx + 6 * S, y0 + hh + 6 * S,
                              fill=FOOT, outline="#221e1c", width=max(1, round(S)))  # 몸 그림의 윤곽과 같은 색·굵기
        c.create_image(x0, y0, anchor="nw", image=img)
        if self.brief or self.has_letter:
            bx, by = info.get("beak", (0.5, 0.5))
            if flip:
                bx = 1 - bx
            (self.draw_paper if self.brief else self.draw_letter)(x0 + bx * hw, y0 + by * hh, line)
        self.draw_umbrella(ox, oy, iw, ih, line)

    def draw_sleep_z(self, x, y, line):
        """머리 위에 하나씩 늘어나는 z"""
        S = self.S
        for i in range((self.frame // 15) % 3 + 1):
            self.draw_z(x + i * 7 * S, y - i * 7 * S, (6 + i * 2) * S, line)

    def draw_mouth(self, shape, ox, oy, flip, line):
        """입 위치(cfg['mouth'])에 입 모양을 덧그림: open 벌린 입 / frown 삐죽 / flat 일자 / smile 웃음"""
        anchor = self.cfg.get("mouth")
        if not anchor:
            return
        c, S = self.canvas, self.S
        mx, my = anchor
        if flip:
            mx = self.iw - mx
        box = self.cfg.get("mouth_box")  # 평소 그림에 입이 그려져 있으면 그 자리를 얼굴 색으로 먼저 덮음
        if box:
            bx0, by0, bx1, by1 = box
            if flip:
                bx0, bx1 = self.iw - bx1, self.iw - bx0
            c.create_rectangle(ox + bx0, oy + by0, ox + bx1, oy + by1, fill=self.cfg.get("face", CREAM), outline="")
        x, y, k = ox + mx, oy + my, self.ih / 110 * S
        w = max(1, round(2 * k))
        if shape == "open":
            c.create_oval(x - 4 * k, y - 3 * k, x + 4 * k, y + 5 * k, fill="#3b2a2a", outline=line, width=1)
            c.create_oval(x - 2.4 * k, y + 1.2 * k, x + 2.4 * k, y + 4.4 * k, fill="#e8776d", outline="")
        elif shape == "frown":
            c.create_line(x - 4.5 * k, y + 1.5 * k, x, y - 1.5 * k, x + 4.5 * k, y + 1.5 * k, smooth=True, fill=line,
                          width=w, capstyle="round")
        elif shape == "smile":
            c.create_line(x - 4.5 * k, y - 1.5 * k, x, y + 2 * k, x + 4.5 * k, y - 1.5 * k, smooth=True, fill=line,
                          width=w, capstyle="round")
        else:  # flat
            c.create_line(x - 4 * k, y, x + 4 * k, y, fill=line, width=w, capstyle="round")

    def draw_image(self, wings, eyes, zz):
        c, S, cfg = self.canvas, self.S, self.cfg
        ox, oy = self.mx, self.mt
        iw, ih = self.iw, self.ih
        line = cfg.get("outline", EYE)
        lw = max(1, round(1.5 * S))

        flip = self.dir > 0
        mouth = None
        if zz:
            if self.img_sleep:
                self.draw_sleeping(ox, oy, flip, line)
                return
            spec = self.pose_overlay.get("sleep", {})  # 자는 그림이 없으면 평소 그림에 눈만 감김
            eyes, mouth = spec.get("eyes", "closed"), spec.get("mouth")
        else:
            pose = self.mood_pose(wings)
            if pose and pose in self.pose_imgs:
                self.draw_mood_pose(pose, ox, oy, flip, line)
                return
            if pose:  # 그림 파일 없이 눈·입 모양만 바꾸는 모습
                spec = self.pose_overlay[pose]
                eyes, mouth = spec.get("eyes", eyes), spec.get("mouth")
        c.create_image(ox, oy, anchor="nw", image=self.img_flip if flip else self.img)

        # 날개 (몸 앞에 그려서 몸통 옆부분을 살짝 덮게)
        if wings != "down" and self.has_wings:
            # 펼친 왼쪽 날개를 위로 들었을 때 기준, 어깨(0,0)에서 바깥은 -x, 위는 -y
            angle = WING_ANGLES[wings]
            k = ih / 110 * S
            sx, sy = ox + WING_SHOULDER * k, oy + 0.55 * ih  # 왼쪽 어깨 (몸 가장자리 살짝 안쪽, 눈보다 아래)
            a = math.radians(angle)
            ca, sa = math.cos(a), math.sin(a)

            def place(shape):
                left = []
                for px, py in shape:
                    left += [sx + (px * ca - py * sa) * k, sy + (px * sa + py * ca) * k]
                right = [2 * ox + iw - v if i % 2 == 0 else v for i, v in enumerate(left)]
                return left, right

            def edge(p, first, last):
                # 다각형 곡선 중 first~last 점 구간만 같은 곡선으로 따라 그리기
                # (곡선은 이웃한 두 점의 중간을 지나므로 양 끝은 중간점에서 시작/끝)
                pts = [(p[i], p[i + 1]) for i in range(0, len(p), 2)]
                mid = lambda u, v: ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)
                seq = [mid(pts[first - 1], pts[first])] + pts[first:last + 1] + [mid(pts[last], pts[last + 1])]
                return [v for xy in seq for v in xy]

            for shape, color, (first, last) in ((WING_SHAPE, cfg.get("wing", BROWN), WING_SHAPE_EDGE),
                                                (WING_GREEN, cfg.get("wing_green", LEAF), WING_GREEN_EDGE)):
                for p in place(shape):
                    # 몸에 겹치는 뿌리 쪽은 테두리 없이 칠하고, 바깥 가장자리에만 테두리
                    c.create_polygon(*p, smooth=True, fill=color, outline="")
                    c.create_line(*edge(p, first, last), smooth=True, fill=line, width=lw,
                                  capstyle="round", joinstyle="round")

        # 표정 덧그리기
        if eyes in ("closed", "dizzy", "happy", "squint", "half"):
            for x0, y0, x1, y1 in cfg.get("eyes", []):
                if flip:
                    x0, x1 = iw - x1, iw - x0
                left_eye = (x0 + x1) / 2 < iw / 2  # 화면에서 왼쪽 눈인지
                if eyes == "half":  # 반쯤 감긴 눈: 눈 위쪽을 눈꺼풀로 덮고, 안쪽(얼굴 가운데 쪽)이 더 내려오게
                    h = y1 - y0
                    lo_in, lo_out = y0 + h * 0.62, y0 + h * 0.36
                    ya, yb = (lo_out, lo_in) if left_eye else (lo_in, lo_out)  # (왼쪽 가장자리, 오른쪽 가장자리) 눈꺼풀 높이
                    c.create_polygon(ox + x0 - 1, oy + y0 - 2, ox + x1 + 1, oy + y0 - 2, ox + x1 + 1, oy + yb, ox + x0 - 1, oy + ya,
                                     fill=cfg.get("face", CREAM), outline="")
                    c.create_line(ox + x0 - 1, oy + ya, ox + x1 + 1, oy + yb, fill=line, width=round(2 * S), capstyle="round")
                    continue
                c.create_oval(ox + x0 - 1, oy + y0 - 1, ox + x1 + 1, oy + y1 + 1,
                              fill=cfg.get("face", CREAM), outline="")
                if eyes == "squint":  # 질끈 감은 눈: 왼쪽 눈은 > , 오른쪽 눈은 <
                    ym = oy + (y0 + y1) / 2
                    xa, xb = (ox + x0, ox + x1) if left_eye else (ox + x1, ox + x0)
                    c.create_line(xa, oy + y0 + 3 * S, xb, ym, xa, oy + y1 - 3 * S, fill=line, width=round(2.2 * S),
                                  capstyle="round", joinstyle="round")
                elif eyes == "happy":
                    # 웃는 눈 ^ 과 눈 아래 바깥쪽 분홍 볼터치
                    my = oy + (y0 + y1) / 2 + 1 * S
                    c.create_line(ox + x0, my + 3 * S, (ox + (x0 + x1) / 2), my - 4 * S, ox + x1, my + 3 * S,
                                  smooth=True, fill=line, width=round(2.2 * S), capstyle="round")
                    outer = x0 if (x0 + x1) / 2 < iw / 2 else x1
                    bx = ox + outer + (-2 if outer == x0 else 2) * S
                    by = oy + y1 + 2 * S
                    c.create_oval(bx - 5 * S, by - 2.5 * S, bx + 5 * S, by + 2.5 * S, fill="#ffa3bb", outline="")
                elif eyes == "closed":
                    my = oy + (y0 + y1) / 2 + 2 * S
                    c.create_line(ox + x0, my - 2 * S, (ox + (x0 + x1) / 2), my + 1 * S, ox + x1, my - 2 * S,
                                  smooth=True, fill=line, width=round(2 * S), capstyle="round")
                else:
                    c.create_line(ox + x0, oy + y0 + 4, ox + x1, oy + y1 - 4, fill=line, width=round(2 * S))
                    c.create_line(ox + x1, oy + y0 + 4, ox + x0, oy + y1 - 4, fill=line, width=round(2 * S))

        if mouth and mouth != "none":
            self.draw_mouth(mouth, ox, oy, flip, line)

        if self.brief or self.has_letter:
            bx, by = cfg.get("beak") or (iw / 2, ih * 0.43)
            if flip:
                bx = iw - bx
            (self.draw_paper if self.brief else self.draw_letter)(ox + bx, oy + by, line)

        self.draw_umbrella(ox, oy, iw, ih, line)

        if zz:
            phase = (self.frame // 15) % 3
            for i in range(phase + 1):
                self.draw_z(ox + iw - 8 * S + i * 7 * S, oy - 2 * S - i * 7 * S, (6 + i * 2) * S, line)

    def run(self):
        def log_error(*exc):  # pythonw 는 오류를 보여 주지 않아서 error.log 에 남김
            import traceback
            try:
                with open(os.path.join(HERE, "error.log"), "a", encoding="utf-8") as fp:
                    fp.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{''.join(traceback.format_exception(*exc))}")
            except OSError:
                pass
        self.root.report_callback_exception = log_error
        self.root.mainloop()
