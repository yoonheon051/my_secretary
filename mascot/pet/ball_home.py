"""집(몬스터볼)·밥그릇·볼 연출"""

import ctypes
import math
import time
import tkinter as tk

from ..constants import KEY
from ..winapi import raise_in_order, user32, win_rect


class BallHomeMixin:
    # ---------- 집: 바닥의 몬스터볼 (밥그릇은 밥 줄 때만 나타남) ----------
    def build_home(self):
        # 밥그릇: 밥 줄 때만 보이는 작은 창 (나몰빼미보다 앞에 보여야 함)
        b = self.bowl_win = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        b.attributes("-transparentcolor", KEY)
        b.configure(bg=KEY)
        self.bowl_canvas = tk.Canvas(b, bg=KEY, highlightthickness=0, bd=0)
        self.bowl_canvas.pack()
        self.bowl_visible = False
        self.bowl_hide_at = 0.0
        self.bowl_geo = ""
        # 몬스터볼 (나몰빼미의 둥지). 나몰빼미가 앉으면 앞쪽 흰 부분이 몸 아래를 가려서,
        # 볼 위를 누르거나 끄는 동작은 나몰빼미에게 그대로 넘겨 주려고 클릭 통과는 아님
        m = self.ball_win = tk.Toplevel(self.root)
        m.overrideredirect(True)
        m.attributes("-topmost", True)
        m.attributes("-transparentcolor", KEY)
        m.configure(bg=KEY)
        self.ball_canvas = tk.Canvas(m, bg=KEY, highlightthickness=0, bd=0)
        self.ball_canvas.pack()
        self.ball_canvas.bind("<ButtonPress-1>", self.ball_press)
        self.ball_canvas.bind("<B1-Motion>", self.ball_motion)
        self.ball_canvas.bind("<ButtonRelease-1>", self.ball_release)
        self.ball_canvas.bind("<Button-3>", self.on_menu)
        self.place_home()
        self.make_click_through(b)  # 밥그릇 뒤의 나몰빼미를 클릭할 수 있게
        b.withdraw()
        self.root.lift()

    def restack(self):
        """화면 앞뒤 순서: 바닥의 열매 < 몬스터볼 < 나몰빼미 (볼로 들어가고 나오는 중엔 볼이 앞) < 밥그릇 < 밥그릇 속 열매 < 말풍선 < 설정 창
        (우클릭 메뉴는 Windows 가 맨 앞에 띄움)"""
        if self.menu_open:
            return  # 메뉴가 떠 있는 동안 건드리면 메뉴가 뒤로 숨을 수 있음
        order = ([it.win for it in self.items if not it.in_bowl]
                 + ([self.root, self.ball_win] if self.ball_front else [self.ball_win, self.root])
                 + ([self.bowl_win] if self.bowl_visible else []) + [it.win for it in self.items if it.in_bowl])
        if self.bubble_until:
            order.append(self.bubble)
        if self.status_win is not None:
            order.append(self.status_win)
        if self.dialog is not None and self.dialog.winfo_exists():
            order.append(self.dialog)
        raise_in_order(order)

    @staticmethod
    def make_click_through(win):
        """마우스 클릭이 이 창을 통과해서 뒤에 있는 창·아이콘이 눌리게 함"""
        try:
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x20 | 0x80000)  # TRANSPARENT | LAYERED
        except Exception:
            pass

    BALL_HOME_X = 100    # 볼 가운데가 주 모니터 왼쪽 끝에서 떨어진 거리 (px@100%): 예전에 나무 뿌리가 있던 자리
    BOWL_SCALE = 0.7     # 밥그릇 크기 배율
    BOWL_R = 26          # 밥그릇 반지름 (그림 좌표)
    BOWL_GAP = 55        # 볼 오른쪽 끝에서 밥그릇 가운데까지 (px@100%)
    EAT_DX = -58         # 먹을 때 나몰빼미 중심이 밥그릇 가운데에서 왼쪽으로 떨어진 거리(px@100%). 밥그릇을 보고 섬

    def place_home(self):
        """주 모니터 왼쪽 아래 바닥에 몬스터볼과 (필요할 때 나타날) 밥그릇 자리를 정함"""
        S = self.S
        x0, base = self.home_area[0], self.home_area[3]
        self.ball_floor = base
        self.ball_cx = x0 + self.BALL_HOME_X * S
        s = self.bowl_s = self.BOWL_SCALE * S
        self.bowl_cx = self.ball_cx + self.BALL_D * S / 2 + self.BOWL_GAP * S
        self.bowl_rest = base - 14 * s  # 열매 아랫면이 밥그릇 안쪽에 쏙 들어가는 높이
        R = self.BOWL_R
        bw, bh = int((2 * R + 8) * s), int(35 * s)
        self.bowl_canvas.config(width=bw, height=bh)
        self.bowl_geo = f"{bw}x{bh}+{int(self.bowl_cx - bw / 2)}+{int(base - 32 * s)}"  # 그릇 바닥이 바닥에 닿게
        self.bowl_win.geometry(self.bowl_geo)
        self.draw_bowl()
        self.place_ball()

    def show_bowl(self):
        """밥 줄 때: 볼 오른쪽에 밥그릇이 나타남"""
        self.bowl_hide_at = time.time() + 4
        if not self.bowl_visible:
            self.bowl_visible = True
            self.bowl_win.geometry(self.bowl_geo)  # 숨겼던 창은 다시 띄울 때 위치가 풀릴 수 있어서 앞뒤로 맞춤
            self.bowl_win.deiconify()
            self.bowl_win.update_idletasks()
            self.bowl_win.geometry(self.bowl_geo)
            self.restack()

    def hide_bowl(self):
        self.bowl_visible = False
        self.bowl_win.withdraw()

    def update_bowl(self, now):
        """다 먹었거나 열매가 없어지면 밥그릇이 사라짐"""
        if self.bowl_visible and now >= self.bowl_hide_at and not any(it.in_bowl for it in self.items):
            self.hide_bowl()

    # ---------- 몬스터볼: 바닥에 놓인 나몰빼미의 둥지 ----------
    BALL_D = 72          # 지름 (px@100%, 화면 배율 S 를 곱함)
    TRAVEL_SCALES = ((1, 1), (5, 6), (2, 3), (1, 2), (2, 5), (1, 3), (1, 4), (1, 6))  # 빨려 들어가며 작아지는 크기 (확대, 축소)
    CLOSE_SEC = 0.22     # 열린 볼이 닫히는 시간
    LID_OPEN = 22       # 볼이 활짝 열린 정도의 기준값 (px@100%, 이 값에서 뚜껑이 끝까지 젖혀짐)
    LID_ANGLE = 1.1      # 활짝 열렸을 때 뚜껑이 뒤로 젖혀지는 각 (rad, 약 63도)
    LID_TILT = 0.5       # 열릴수록 위에서 내려다보는 각 (rad, 약 29도): 입구 안쪽이 보이게
    CAPTURE_SEC = 1.0   # 볼 속으로 빨려 들어가는 시간
    RELEASE_SEC = 1.2    # 볼이 열리고 나몰빼미가 튀어나오는 시간 (앞 20% 는 볼만 열림)
    SHAKE_SEC = 1.7      # 들어간 뒤 볼이 흔들리는 시간
    # 둥지에 앉은 것으로 치는 상태 (볼 앞쪽 흰 부분이 나몰빼미 몸 아래를 가림)
    AT_BALL_STATES = ("idle", "sleep", "happy", "pet", "land", "toball", "capture", "release")  # 볼 자리에서 이럴 땐 볼 위에 서 있음
    PERCH_LIFT = BALL_D - 8  # 볼 위에 설 때 나몰빼미를 올리는 양 (px@100%)
    PERCH_SEC = 0.25         # 볼 위로 오르내리는 데 걸리는 시간
    # 친밀도 레벨이 이 값 이상이면 그 볼 (필요한 레벨, 이름). 단계를 바꾸거나 늘리려면 여기만 고치면 됨
    BALL_TIERS = ((1, "몬스터볼"), (10, "슈퍼볼"), (20, "하이퍼볼"), (30, "마스터볼"), (40, "프리미어볼"))
    # 볼마다 (뚜껑 색, 무늬 색, 뚜껑의 반짝임 색, 가운데 띠 색: None 이면 검정)
    BALL_STYLES = ("plain", "super", "hyper", "master", "plain")  # 포켓몬을 불러오면 그 포켓몬의 볼 설정으로 바뀜
    BALL_COLORS = (("#e5322d", None, "#ff9a92", None),
                   ("#2f6fd8", "#e5322d", "#a9c8ff", None),
                   ("#2d2d33", "#ffd23f", "#9a9aab", None),
                   ("#8e44c6", "#ff8fdc", "#d9b3f5", None),
                   ("#f6f6f6", None, "#dcdcdc", "#d9382f"))  # 프리미어볼: 온통 흰색에 빨간 띠

    def ball_tier(self, level=None):
        """지금 친밀도에 맞는 볼 단계 번호 (0=몬스터볼 … 4=프리미어볼)"""
        lv = self.level() if level is None else level
        return max(i for i, (need, _) in enumerate(self.BALL_TIERS) if lv >= need or i == 0)

    def place_ball(self):
        """바닥, 나몰빼미가 앉는 자리 (ball_cx) 에 볼 창을 놓음"""
        S = self.S
        self.ball_r = self.BALL_D * S / 2
        d = int(self.BALL_D * S)
        pad, zroom = int(18 * S), int((self.LID_OPEN + 36) * S)  # 좌우 여유(빛줄기), 위쪽 여유(열린 뚜껑·빛줄기·zZ)
        w, h = d + 2 * pad, zroom + d + 3
        self.ball_zroom = zroom
        bottom = self.ball_floor  # 작업 표시줄 바로 위 바닥에 놓임
        self.ball_cy = bottom - self.ball_r
        self.ball_size = (w, h)
        self.ball_canvas.config(width=w, height=h)
        self.ball_win.geometry(f"{w}x{h}+{int(self.ball_cx - w / 2)}+{int(bottom - zroom - d)}")
        self.ball_sig = None

    def draw_ball(self, tilt=0.0, lid=0.0, glow=False, burst=-1.0, zstep=-1,
                  canvas=None, tier=None, r=None, w=None, zroom=None, sprite=None):
        """몬스터볼 그리기.
        tilt 흔들림 각도(도), lid 뚜껑이 들린 높이(px), glow 버튼에 빨간 불, burst 열린 뒤 지난 시간(빛줄기), zstep zZ 개수-1.
        canvas·tier·r·w·zroom 을 주면 집의 볼 대신 그 캔버스에 그 단계의 볼을 그림 (상태 카드의 미리보기)"""
        c, S = canvas or self.ball_canvas, self.S
        r = self.ball_r if r is None else r
        c.delete("all")
        tier = self.ball_tier() if tier is None else tier
        top_c, mark_c, _shine_c, band_c = self.BALL_COLORS[tier]  # 세 번째(반짝임 색)는 지금 안 씀
        style = self.BALL_STYLES[tier]
        dark, lw = "#1b1b1b", max(1, round(2 * S))
        low_c = "#e9e9e9" if band_c else "#f5f5f5"  # 아랫부분 색 (프리미어볼은 뚜껑과 구분되게 살짝 회색빛)
        w = self.ball_size[0] if w is None else w
        zroom = self.ball_zroom if zroom is None else zroom
        cx, cy = w / 2 + tilt * 0.12 * S, zroom + r
        if round(lid) == 0:  # 0.5px 도 안 열린 건 닫힌 것: 화면 갱신 비교(round(lid))와 같은 기준으로 맞춤
            lid = 0.0
        cl = cy - lid  # 뚜껑 중심의 높이
        f = min(1.0, lid / (self.LID_OPEN * S)) if lid > 0 else 0.0  # 열린 정도 0~1
        if f > 0:
            self.draw_open_ball(c, cx, cy, r, f, top_c, low_c, dark, lw, sprite, band_c, mark_c, style)
        else:
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=180 + tilt, extent=180, style="chord",
                         fill=low_c, outline=dark, width=lw)  # 아래 흰 반구
            c.create_arc(cx - r, cl - r, cx + r, cl + r, start=tilt, extent=180, style="chord",
                         fill=top_c, outline=dark, width=lw)  # 위 뚜껑
            ca, sa = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
            rot = lambda dx, dy: (cx + dx * ca + dy * sa, cl - dx * sa + dy * ca)  # 뚜껑 중심 기준 (위쪽이 -y), 흔들림만큼 회전
            rr = r - lw

            def band(a0, a1, inner):  # 뚜껑 가장자리를 따라가는 띠 무늬
                c.create_arc(cx - rr, cl - rr, cx + rr, cl + rr, start=a0 + tilt, extent=a1 - a0,
                             style="pieslice", fill=mark_c, outline="")
                ri = rr * inner
                c.create_arc(cx - ri, cl - ri, cx + ri, cl + ri, start=a0 + tilt, extent=a1 - a0,
                             style="pieslice", fill=top_c, outline="")
            if style == "super":  # 슈퍼볼: 파란 뚜껑 양옆의 빨간 띠
                band(12, 44, 0.5)
                band(136, 168, 0.5)
            elif style == "hyper":  # 하이퍼볼: 검은 뚜껑에 노란 띠
                band(10, 44, 0.6)
                band(136, 170, 0.6)
                band(72, 108, 0.68)
            elif style == "master":  # 마스터볼: 보라 뚜껑, 분홍 동그라미 둘과 M
                for sx in (-1, 1):
                    px, py = rot(sx * 0.62 * r, -0.3 * r)
                    c.create_oval(px - 0.2 * r, py - 0.2 * r, px + 0.2 * r, py + 0.2 * r, fill=mark_c, outline=dark, width=1)
                pts = []
                for dx, dy in ((-0.2, -0.34), (-0.2, -0.74), (0.0, -0.5), (0.2, -0.74), (0.2, -0.34)):
                    pts += rot(dx * r, dy * r)
                c.create_line(*pts, fill=mark_c, width=max(2, round(2.6 * S)), joinstyle="miter", capstyle="round")
            a = math.radians(tilt)
            dx, dy = r * math.cos(a), -r * math.sin(a)
            bw = lw + max(1, round(S))
            if band_c:  # 프리미어볼: 검은 테두리 선 사이에 빨간 띠
                c.create_line(cx - dx, cy - dy, cx + dx, cy + dy, fill=dark, width=bw + 2)
                c.create_line(cx - dx, cy - dy, cx + dx, cy + dy, fill=band_c, width=bw)
            else:
                c.create_line(cx - dx, cy - dy, cx + dx, cy + dy, fill=dark, width=bw)  # 가운데 띠
            if lid <= 0:
                c.create_oval(cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3, fill="#ffffff",
                              outline=band_c or dark, width=lw)
                c.create_oval(cx - r * 0.15, cy - r * 0.15, cx + r * 0.15, cy + r * 0.15,
                              fill="#ff6a5c" if glow else "#e6e6e6", outline="#666666", width=1)  # 버튼
        if 0 <= burst < 0.7:  # 열리거나 단계가 오를 때 위로 퍼지는 빛줄기
            ln, r1 = (5 + 9 * burst / 0.7) * S, r * (1.12 + 0.5 * f) + burst * 4 * S
            cyr = cy - 0.3 * r * f
            for i in range(13):
                ang = math.radians(-5 + i * 15)
                c.create_line(cx + r1 * math.cos(ang), cyr - r1 * math.sin(ang),
                              cx + (r1 + ln) * math.cos(ang), cyr - (r1 + ln) * math.sin(ang),
                              fill="#ffd23f" if i % 2 else "#fff0a0", width=lw)
        for i in range(zstep + 1):  # 자는 동안 볼 위로 올라가는 zZ
            self.draw_z(cx + (8 + i * 7) * S, zroom - 4 * S - i * 7 * S, (6 + i * 2) * S, "#5b6b5d", canvas=c)

    def draw_open_ball(self, c, cx, cy, r, f, top_c, low_c, dark, lw, sprite=None, band_c=None, mark_c=None, style="plain"):
        """열린 볼: 노트북·캐스터네츠처럼 뒤쪽 경첩을 축으로 뚜껑이 뒤로 젖혀지고, 앞쪽이 벌어져 안쪽이 보임.
        f = 열린 정도 0~1. 볼 중심 기준 3D 좌표(y 위, z 보는 쪽)에서 계산해 화면 위쪽에서 살짝 내려다본 모습으로 그림"""
        th, ph = f * self.LID_ANGLE, f * self.LID_TILT  # 뚜껑 젖힌 각, 내려다보는 각
        cth, sth, cph, sph = math.cos(th), math.sin(th), math.cos(ph), math.sin(ph)

        def proj(x, y, z):
            return cx + x, cy - (y * cph - z * sph)

        def lid_pt(x, y, z):  # 뒤쪽 경첩 (y=0, z=-r) 을 축으로 뚜껑 점을 th 만큼 젖힘
            u, v = z + r, y
            return proj(x, u * sth + v * cth, u * cth - v * sth - r)

        def hull(pts):  # 볼록 껍질 (반구의 화면 그림자)
            pts = sorted(set(pts))
            def half(seq):
                out = []
                for p in seq:
                    while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                        out.pop()
                    out.append(p)
                return out
            lo, up = half(pts), half(pts[::-1])
            return [q for p in lo[:-1] + up[:-1] for q in p]

        ring = [(r * math.cos(math.radians(b)), 0.0, r * math.sin(math.radians(b))) for b in range(0, 360, 10)]
        # 뚜껑: 바깥 둥근 면 (뒤로 젖혀져 위쪽에 보임) + 안쪽 면 (보는 쪽으로 향함)
        dome = [lid_pt(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0.0) for a in range(0, 181, 10)]
        dome += [lid_pt(*p) for p in ring] + [lid_pt(0.0, r, 0.0)]
        c.create_polygon(*hull(dome), fill=top_c, outline=dark, width=lw)

        # 뚜껑 바깥 무늬: 닫혔을 때 보이던 그림 좌표(x, y)를 둥근 면 위의 점으로 옮겨 같이 젖힘 (보이지 않는 쪽은 뺌)
        def dome_pt(x, y):
            z = math.sqrt(max(0.0, r * r - x * x - y * y))
            u, v = z, y  # 면의 바깥쪽 방향 (x, y, z)/r 도 같이 젖힘
            ny, nz = u * sth + v * cth, u * cth - v * sth
            return lid_pt(x, y, z), (ny * sph + nz * cph) / r > 0.06

        def mark(pts, **kw):  # pts: 닫힌 그림 좌표 (위가 +y). 보이는 점들로 다각형을 그림
            vis = [p for p, ok in (dome_pt(x, y) for x, y in pts) if ok]
            if len(vis) >= 3:
                c.create_polygon(*[q for p in vis for q in p], **kw)

        def arc_pts(rad, a0, a1, n=8):
            return [(rad * math.cos(math.radians(a0 + (a1 - a0) * i / n)), rad * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
                    for i in range(n + 1)]
        rr = r - lw
        if style in ("super", "hyper") and mark_c:  # 슈퍼볼·하이퍼볼의 띠
            bands = ((12, 44, 0.5), (136, 168, 0.5)) if style == "super" else ((8, 46, 0.42), (134, 172, 0.42), (76, 104, 0.68))
            for a0, a1, inner in bands:
                mark(arc_pts(rr, a0, a1) + arc_pts(rr * inner, a1, a0), fill=mark_c, outline="")
        elif style == "master" and mark_c:  # 마스터볼: 분홍 동그라미 둘과 M
            for sx in (-1, 1):
                mark([(sx * 0.62 * r + 0.2 * r * math.cos(math.radians(a)), 0.3 * r + 0.2 * r * math.sin(math.radians(a)))
                      for a in range(0, 360, 30)], fill=mark_c, outline=dark, width=1)
            m = [dome_pt(dx * r, dy * r) for dx, dy in ((-0.2, 0.34), (-0.2, 0.74), (0.0, 0.5), (0.2, 0.74), (0.2, 0.34))]
            if all(ok for _, ok in m):
                c.create_line(*[q for p, _ in m for q in p], fill=mark_c, width=max(2, round(2.6 * self.S)),
                              joinstyle="miter", capstyle="round")
        if math.sin(th - ph) > 0.05:  # 안쪽 면이 보이는 만큼 (젖힌 각이 내려다보는 각보다 클 때)
            inner = [q for p in ring for q in lid_pt(*p)]
            c.create_polygon(*inner, fill="#ece4c6", outline=dark, width=lw)
            c.create_polygon(*[q for p in ring for q in lid_pt(p[0] * 0.72, 0.0, p[2] * 0.72)], fill="#f6f0da", outline="")
        # 아랫부분(그릇): 아래 반구 + 입구 타원, 입구 안쪽은 빛이 새어 나옴
        bowl = [proj(r * math.cos(math.radians(a)), -r * math.sin(math.radians(a)), 0.0) for a in range(0, 181, 10)]
        bowl += [proj(*p) for p in ring]
        c.create_polygon(*hull(bowl), fill=low_c, outline=dark, width=lw)
        c.create_polygon(*[q for p in ring for q in proj(*p)], fill="#fff0b0", outline=dark, width=lw)
        c.create_polygon(*[q for p in ring for q in proj(p[0] * 0.7, 0.0, p[2] * 0.7)], fill="#fffbe0", outline="")
        if band_c:  # 프리미어볼: 입구 둘레의 빨간 띠
            c.create_polygon(*[q for p in ring for q in proj(*p)], fill="", outline=band_c, width=max(2, lw))
            if math.sin(th - ph) > 0.05:
                c.create_polygon(*[q for p in ring for q in lid_pt(*p)], fill="", outline=band_c, width=max(2, lw))
        hx, hy = proj(0.0, 0.0, -r)  # 경첩: 뒤쪽 가장자리에 마디 두 개
        hw, hh = r * 0.2, max(2.0, r * 0.07)
        for sx in (-1, 1):
            c.create_rectangle(hx + sx * r * 0.18 - hw / 2, hy - hh, hx + sx * r * 0.18 + hw / 2, hy + hh,
                               fill="#8d8d8d", outline=dark, width=max(1, lw // 2))
        if sprite:  # 볼 속으로 들어가거나 나오는 나몰빼미: 뚜껑·입구 앞, 그릇 앞쪽 테두리 뒤
            img, sx, sy, sw, sh = sprite[:5]
            S = self.S
            c.create_polygon(cx, cy, sx - sw * 0.4, sy - sh * 0.45, sx + sw * 0.4, sy + sh * 0.45,
                             fill="#ff5a4d", stipple="gray25", outline="")
            c.create_image(sx, sy, image=img)
            for grow, color in ((0.55, "#ff3b30"), (0.7, "#ff9a8f")):
                c.create_oval(sx - sw * grow, sy - sh * grow, sx + sw * grow, sy + sh * grow,
                              outline=color, width=max(2, round(3 * S)))
            front = [proj(r * math.cos(math.radians(a)), -r * math.sin(math.radians(a)), 0.0) for a in range(0, 181, 10)]
            front += [proj(r * math.cos(math.radians(b)), 0.0, r * math.sin(math.radians(b))) for b in range(180, -1, -10)]
            c.create_polygon(*[q for p in front for q in p], fill=low_c, outline=dark, width=lw)

    def ball_wanted(self):
        """나몰빼미가 볼 안에 있어야 하는지: 재우기 중이거나, 종료 예고 중이거나, 종료 명령을 보낸 직후"""
        return (self.pomo_phase == "focus" or self.shutdown_at is not None
                or time.time() < self.ball_hold_until)

    def update_ball(self, now):
        """나몰빼미를 볼로 보낼지·꺼낼지 정하고, 둥지에 앉았는지에 맞춰 볼 모양·앞뒤 순서를 갱신"""
        wanted, st = self.ball_wanted(), self.state
        if st not in ("capture", "release") and (self.travel_room or self.ball_front):
            self.set_ball_front(False)
            self.set_travel_room(False)
        if wanted and not self.in_ball:
            if st in ("idle", "walk", "sleep", "home", "land", "happy", "eat", "goto", "pet"):
                self.visit = None  # 놀러 간 곳이 있었어도 취소 (볼이 집이라서)
                self.set_state("toball")  # 날고 있거나 집어 든 중이면 내려앉은 뒤에
        elif not wanted:
            if st == "toball":
                self.set_state("idle", 1)
            elif self.in_ball and st == "focus":
                self.start_release(now)
            elif self.in_ball and st not in ("capture", "release"):  # 볼 안인데 다른 상태가 됐으면 (꼬여서 볼이 계속 열려 있는 일 방지) 꺼냄
                self.start_release(now)
        # 바닥의 볼 자리에 있으면 볼 위에 서 있음 (창 높이: 볼 위는 PERCH_LIFT 만큼 위, 바닥은 0. 오르내릴 땐 부드럽게)
        at_ball = (not self.in_ball and self.on_home_floor() and self.state in self.AT_BALL_STATES
                   and abs(self.x + self.W / 2 - self.ball_cx) <= 9 * self.S)
        S = self.S
        tgt = -int(self.PERCH_LIFT * S) if at_ball else 0
        if self.state in self.AT_BALL_STATES + ("walk", "home", "goto", "eat"):
            dt = min(0.1, max(0.0, now - self.sink_t))
            stepv = max(1, int(self.PERCH_LIFT * S * dt / self.PERCH_SEC))
            self.sink_now += max(-stepv, min(stepv, tgt - self.sink_now))
        else:
            self.sink_now = tgt  # 집어 들거나 날 때 등은 바로
        self.sink_t = now
        tilt = lid = 0.0
        glow, burst = False, -1.0
        fx = self.ball_fx
        if fx:
            t, S = now - fx["t0"], self.S
            if fx["kind"] == "open":
                lid, glow = min(1.0, t / 0.25) * self.LID_OPEN * S, True
            elif fx["kind"] == "close":  # 열려 있던 볼이 딸깍 닫힘
                if t >= self.CLOSE_SEC:
                    self.ball_fx = None
                else:
                    lid = (1 - t / self.CLOSE_SEC) ** 2 * self.LID_OPEN * S
            elif fx["kind"] == "shake":
                if t < self.CLOSE_SEC:  # 나몰빼미가 들어간 직후엔 먼저 닫힘
                    lid = (1 - t / self.CLOSE_SEC) ** 2 * self.LID_OPEN * S
                elif t >= self.SHAKE_SEC:
                    self.ball_fx = None
                elif int(t / 0.5) < 3:  # 세 번 흔들
                    tilt = (22 if int(t / 0.5) % 2 == 0 else -22) * math.sin(math.pi * (t % 0.5) / 0.5)
                else:
                    glow = True  # 딸깍 하고 빨간 불이 켜짐
            elif fx["kind"] == "burst":
                lid, glow, burst = min(1.0, t / 0.15) * self.LID_OPEN * S, True, t
            elif fx["kind"] == "flash":  # 볼 단계가 오를 때 (뚜껑은 그대로, 빛줄기만)
                if t >= 0.8:
                    self.ball_fx = None
                else:
                    burst = t
        inside = self.in_ball and self.ball_fx is None
        if inside:
            glow = int(now * 1.6) % 2 == 0  # 자는 동안 버튼이 천천히 깜빡
        zstep = (self.frame // 15) % 3 if inside else -1
        sprite = self.travel_sprite()
        sig = (self.ball_tier(), round(tilt), round(lid), glow, round(burst * 20) if burst >= 0 else -1, zstep,
               None if sprite is None else (sprite[5], round(sprite[1]), round(sprite[2])))
        if sig != self.ball_sig:
            self.ball_sig = sig
            self.draw_ball(tilt, lid, glow, burst, zstep, sprite=sprite)

    def on_home_floor(self):
        """주 모니터 바닥에 서 있는지 (몬스터볼이 있는 바닥)"""
        return (self.surface is None and abs(self.y - self.ground()) < 3
                and self.monitor_at(self.x + self.W / 2) == self.home_area)

    def step_toball(self, now):
        """볼(둥지)로 감: 둥지에 앉아 있으면 빨려 들어가고, 같은 바닥이면 걸어서, 그 밖에는 날아서"""
        S = self.S
        d = self.ball_cx - (self.x + self.W / 2)
        if self.on_home_floor() and abs(d) <= 9 * S:
            self.cap_t0 = now
            self.ball_fx = {"kind": "open", "t0": now}
            self.set_travel_room(True)
            self.set_state("capture")
        elif self.on_home_floor() and abs(d) <= 320 * S:
            self.dir = 1 if d > 0 else -1
            self.x += self.dir * min(2.0 * S * self.k, abs(d))
        else:
            self.fly_to(self.ball_cx, self.ball_floor)

    def set_travel_room(self, on):
        """볼로 들어가고 나오는 동안만 나몰빼미 창을 아래로 늘려서, 볼 한가운데까지 가도 창 끝에서 잘리지 않게"""
        if on == self.travel_room:
            return
        self.travel_room = on
        self.canvas.config(height=self.H + (int(self.BALL_D * self.S * 0.6) if on else 0))

    def set_ball_front(self, front):
        """볼 속으로 들어가는 뒤쪽 절반은 볼이 나몰빼미 앞 (볼 테두리 안으로 쏙 들어가는 것처럼 보이게)"""
        if front != self.ball_front:
            self.ball_front = front
            self.restack()

    def finish_capture(self, now):
        self.set_ball_front(False)
        self.set_travel_room(False)
        self.in_ball = True
        self.root.withdraw()
        self.set_state("focus")
        self.ball_fx = {"kind": "shake", "t0": now}

    def start_release(self, now):
        self.rel_t0 = now
        self.ball_fx = {"kind": "burst", "t0": now}
        self.set_state("release")

    def show_pet(self):
        """볼에서 나온 나몰빼미 창을 둥지 자리에 다시 보이게 함"""
        self.x = self.ball_cx - self.W / 2
        self.surface = self.left_surface = None
        self.dir = -1
        self.pick_monitor()
        self.y = self.ground()
        self.in_ball = False
        self.sink_now = -int(self.PERCH_LIFT * self.S)
        self.ball_sig = None
        self.set_travel_room(True)
        pos = f"+{int(self.x)}+{int(self.y) + self.sink_now}"
        self.root.geometry(pos)
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.geometry(pos)
        self.last_pos = self.last_sig = None
        self.restack()

    def ball_press(self, e):
        """볼을 눌렀을 때 (나몰빼미는 볼 위에 따로 서 있어서 나몰빼미를 누르면 나몰빼미 창이 받음)"""
        self.ball_route = "ball"

    def ball_motion(self, e):
        if self.ball_route == "pet":
            self.on_motion(e)

    def ball_release(self, e):
        route, self.ball_route = self.ball_route, None
        if route == "pet":
            self.on_release(e)
        elif route == "ball":
            self.ball_click()

    def ball_click(self):
        """빈 볼을 누르면 재우기 시작. 자는 중이면 남은 시간을 알려 주고, 한 번 더 누르면 깨움"""
        now = time.time()
        if self.state in ("toball", "capture", "release"):
            return
        if self.in_ball:
            if self.pomo_phase == "focus":
                if now < self.ball_click_until:
                    self.ball_click_until = 0.0
                    self.pomo_stop()
                else:
                    left = max(0, int(self.pomo_end - now))
                    self.ball_click_until = now + 6
                    self.say(f"쿨쿨... {max(1, math.ceil(left / 60))}분 뒤에 일어날게요.\n(한 번 더 누르면 깨워요)", 6)
            return
        if self.pomo_phase != "focus":
            self.pomo_start()

    def travel_pose(self):
        """볼로 들어가거나 나오는 나몰빼미의 지금 모습 (나몰빼미 창 안 좌표): 진행도 q, 크기 단계, 그림 중심, 크기, 볼 한가운데"""
        S = self.S
        q = self.travel if self.state == "capture" else 1.0 - self.travel  # 0=서 있던 자리, 1=볼 속
        flip = self.dir > 0
        steps = self.img_travel[flip]
        idx = min(len(steps) - 1, int(q * len(steps)))
        z, k = self.TRAVEL_SCALES[idx]
        sc = z / k
        ih = self.ih
        c0x, c0y = self.W / 2, self.mt + ih / 2  # 서 있을 때 그림 한가운데
        bx = self.ball_cx - self.x
        by = self.ball_cy - self.y - self.sink_now  # 볼 입구 한가운데
        ty = by + 0.55 * self.ball_r  # 끝에는 그릇 속으로 가라앉음
        e = q * q * (3 - 2 * q)
        cx = c0x + (bx - c0x) * e
        cy = c0y + (ty - c0y) * e - math.sin(math.pi * q) * 10 * S
        return {"q": q, "idx": idx, "img": steps[idx], "cx": cx, "cy": cy,
                "sw": self.iw * sc, "sh": ih * sc, "bx": bx, "by": by}

    def travel_sprite(self):
        """볼 속으로 들어가는 뒤쪽 절반(q>=0.5)은 볼 그림 안에서 그림: 뚜껑 앞·그릇 앞쪽 테두리 뒤에 끼게 (볼 좌표). 아니면 None"""
        if self.state not in ("capture", "release") or self.in_ball:
            return None
        p = self.travel_pose()
        if p["q"] < 0.5:
            return None
        ox = self.x - int(self.ball_cx - self.ball_size[0] / 2)
        oy = int(self.y) + self.win_bob + self.sink_now - int(self.ball_floor - self.ball_zroom - int(self.BALL_D * self.S))
        return (p["img"], p["cx"] + ox, p["cy"] + oy, p["sw"], p["sh"], p["idx"])

    def draw_travel(self):
        """볼 속으로 빨려 들어가거나 튀어나오는 모습: 작아지며 볼 한가운데로 모이고 빨간 빛을 띰
        (앞쪽 절반만 여기서 그리고, 볼 입구로 들어가는 뒤쪽 절반은 draw_open_ball 이 그림)"""
        c, S = self.canvas, self.S
        p = self.travel_pose()
        if p["q"] >= 0.5:
            return
        cx, cy, sw, sh, bx, by = p["cx"], p["cy"], p["sw"], p["sh"], p["bx"], p["by"]
        c.create_polygon(bx, by, cx - sw * 0.4, cy - sh * 0.45, cx + sw * 0.4, cy + sh * 0.45,
                         fill="#ff5a4d", stipple="gray25", outline="")  # 볼에서 뻗는 빛줄기
        c.create_image(cx, cy, image=p["img"])
        # 빨간 빛: 채우면 나몰빼미가 가려져서 (이 PC 는 반투명 채우기가 안 됨) 테두리 고리로
        for grow, color in ((0.55, "#ff3b30"), (0.7, "#ff9a8f")):
            c.create_oval(cx - sw * grow, cy - sh * grow, cx + sw * grow, cy + sh * grow,
                          outline=color, width=max(2, round(3 * S)))

    def draw_bowl(self):
        """밥그릇 (안쪽은 진하게, 앞에 나뭇잎 무늬). 그림 좌표는 그릇 가운데가 x=0, 바닥면이 y=0"""
        c, s = self.bowl_canvas, self.bowl_s
        c.delete("all")
        lw = max(1, round(2 * s))
        R = self.BOWL_R

        def P(*pts):  # 그림 좌표 → 밥그릇 창 좌표
            return [(v + R + 4) * s if i % 2 == 0 else (v + 30) * s for i, v in enumerate(pts)]

        dark, bowl, bowl_d, bowl_in = "#4e3218", "#e9845e", "#8a3f24", "#7a3a24"
        c.create_arc(*P(-R, -42, R, 2), start=180, extent=180, style="chord",
                     fill=bowl, outline=dark, width=lw)                       # 그릇 몸통 (아래 반원)
        c.create_oval(*P(-R - 2, -25, R + 2, -16), fill="#f3a07f", outline=dark, width=lw)  # 테두리
        c.create_oval(*P(-R + 4, -24, R - 4, -18), fill=bowl_in, outline="")             # 안쪽
        c.create_line(*P(-R + 7, -9, -6, -3), smooth=True, fill="#ffd2bf", width=lw)     # 반짝임
        c.create_oval(*P(4, -11, 16, -4), fill="#58b84f", outline=bowl_d, width=1)       # 나뭇잎 무늬

    def surf_rect(self, surface):
        """발판의 (l, t, r, b). 보이는 앱 창이면 그 영역, 아니면 None (바닥은 발판이 아님)"""
        if surface is None or user32 is None or not self.perch_var.get():
            return None
        rect = win_rect(surface)
        if rect and user32.IsZoomed(surface):
            return None
        return rect
