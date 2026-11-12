"""우클릭 상태 카드"""

import ctypes
import math
import random
import time
import tkinter as tk
from datetime import date, datetime

from ..constants import GRUMPY_AT, HUNGRY_AT, UNIT, VISIT_PLAYED
from ..ui import (
    UI_ACCENT,
    UI_BG,
    UI_HOVER,
    UI_LINE,
    UI_SKY,
    UI_SUB,
    UI_TEXT,
    UI_TRACK,
)


class StatusCardMixin:
    # ---------- 상태 카드 ----------
    CARD_BG, CARD_LINE, CARD_TEXT, CARD_SUB = UI_BG, UI_LINE, UI_TEXT, UI_SUB
    CARD_TRACK, CARD_HOVER, CARD_LOW = UI_TRACK, UI_HOVER, "#d93025"
    # 배부름은 열매 주황, 기분은 볼터치 분홍, 친밀도는 하늘색 (비행 타입)
    CARD_BARS = (("full", "배부름", "#cf8a48"), ("mood", "기분", "#c77790"), ("affection", "친밀도", UI_SKY))

    def show_status(self):
        """상태 카드: 배부름·기분·친밀도 막대 + 오늘 정보 + 바로 쓰는 버튼.
        나몰빼미 옆에 뜨고, 다시 누르거나 카드 밖을 클릭하면 닫힘"""
        if self.status_win is not None:
            self.close_status()
            return
        S, BG, TX, SUB = self.S, self.CARD_BG, self.CARD_TEXT, self.CARD_SUB
        font, small = ("Malgun Gothic", 10), ("Malgun Gothic", 9)
        w = self.status_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=self.CARD_LINE)  # 1px 테두리
        f = tk.Frame(w, bg=BG, padx=int(14 * S), pady=int(12 * S))
        f.pack(padx=1, pady=1)

        head = tk.Frame(f, bg=BG)
        head.pack(fill="x")
        title = tk.Label(head, text=self.species["name"], font=("Malgun Gothic", 11, "bold"), bg=BG, fg=TX, cursor="hand2")
        title.pack(side="left")
        title.bind("<Enter>", lambda e: title.config(font=("Malgun Gothic", 11, "bold underline")))  # 눌러서 도감을 여는 글자
        title.bind("<Leave>", lambda e: title.config(font=("Malgun Gothic", 11, "bold")))
        title.bind("<Button-1>", lambda e: (self.close_status(), self.root.after(30, self.show_collection)))
        self.card_lv = tk.Label(head, font=("Malgun Gothic", 8, "bold"), bg=UI_ACCENT, fg="white", padx=6,
                                cursor="hand2")
        self.card_lv.pack(side="left", padx=(6, 0))
        self.card_lv.bind("<Button-1>", lambda e: self.toggle_ball_preview())
        self.card_ball = None  # 배지를 누르면 열리는 '다음 볼 미리보기'
        self.card_head = head
        close = tk.Label(head, text="✕", font=small, bg=BG, fg=SUB, cursor="hand2")
        close.pack(side="right", padx=(10, 0))
        close.bind("<Button-1>", lambda e: self.close_status())
        self.card_mood = tk.Label(head, font=small, bg=BG, fg=SUB)
        self.card_mood.pack(side="right")

        bars = tk.Frame(f, bg=BG)
        bars.pack(fill="x", pady=(10, 0))
        bw, bh = int(160 * S), max(6, int(8 * S))
        self.card_bars = {}
        for r, (key, name, color) in enumerate(self.CARD_BARS):
            tk.Label(bars, text=name, font=font, bg=BG, fg=TX, width=5, anchor="w").grid(row=r, column=0, pady=2)
            c = tk.Canvas(bars, width=bw, height=bh, bg=self.CARD_TRACK, highlightthickness=0, bd=0)
            c.grid(row=r, column=1, padx=8)
            val = tk.Label(bars, font=font, bg=BG, fg=TX, width=5, anchor="e")
            val.grid(row=r, column=2)
            self.card_bars[key] = (c, c.create_rectangle(0, 0, 0, bh, fill=color, width=0), val, color, bw, bh)

        tk.Frame(f, height=1, bg=UI_LINE).pack(fill="x", pady=(10, 8))
        self.card_info = tk.Frame(f, bg=BG)
        self.card_info.pack(fill="x")
        self.card_lines = None

        self.card_btns = []
        rows = ((("밥 주기", self.feed), ("놀아주기", self.play), ("재우기", self.toggle_pomo)),
                (("일정·업무 ▾", self.schedule_menu), ("설정·기타 ▾", self.more_menu)))
        for r, row in enumerate(rows):
            btns = tk.Frame(f, bg=BG)
            btns.pack(fill="x", pady=(10 if r == 0 else 4, 0))
            for i, (text, cmd) in enumerate(row):
                btns.columnconfigure(i, weight=1, uniform="b")
                edge = tk.Frame(btns, bg=self.CARD_LINE)
                edge.grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else 3, 0))
                b = tk.Label(edge, text=text, font=small, bg=BG, fg=TX, pady=3, cursor="hand2")
                b.pack(fill="x", padx=1, pady=1)
                # 누른 버튼에서 손을 뗄 때 실행 (누르는 순간 메뉴를 띄우면 손을 떼면서 바로 닫힐 수 있음)
                if r == 0:
                    act = lambda c=cmd: (c(), self.refresh_status(force=True))
                else:  # 버튼 바로 아래에 메뉴를 띄움
                    act = lambda b=b, c=cmd: self.popup_menu(c(), b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
                b.bind("<ButtonRelease-1>", lambda e, b=b, a=act: a()
                       if 0 <= e.x < b.winfo_width() and 0 <= e.y < b.winfo_height() else None)
                b.bind("<Enter>", lambda e, b=b: b.config(bg=self.CARD_HOVER))
                b.bind("<Leave>", lambda e, b=b: b.config(bg=BG))
                self.card_btns.append(b)

        self.refresh_status(force=True)
        self.place_status()
        self.card_mouse = self.mouse_down()  # 메뉴를 누르던 클릭을 '카드 밖 클릭'으로 잘못 읽지 않게
        self.restack()
        if self.has_schedule_source and time.time() - self.today_at > 300:
            self.gcal_run("status_today", self.gather_today)

    def close_status(self):
        if self.status_win is not None:
            self.status_win.destroy()
            self.status_win = self.card_size = self.card_ball = None

    def toggle_ball_preview(self):
        """상태 카드의 'Lv · 볼 이름' 배지를 누르면 지금 볼과 다음에 바뀔 볼을 보여 주고, 다시 누르면 접음"""
        if self.status_win is None:
            return
        if self.card_ball is not None:
            self.card_ball.destroy()
            self.card_ball = None
        else:
            S, BG, TX, SUB = self.S, self.CARD_BG, self.CARD_TEXT, self.CARD_SUB
            small = ("Malgun Gothic", 9)
            box = self.card_ball = tk.Frame(self.card_head.master, bg=UI_HOVER, padx=int(10 * S), pady=int(8 * S))
            box.pack(fill="x", pady=(8, 0), after=self.card_head)
            cur = self.ball_tier()
            nxt = cur + 1 if cur + 1 < len(self.BALL_TIERS) else None
            row = tk.Frame(box, bg=UI_HOVER)
            row.pack()
            d = int(52 * S)

            def show(col, tier, title):
                cell = tk.Frame(row, bg=UI_HOVER)
                cell.grid(row=0, column=col, padx=int(8 * S))
                cv = tk.Canvas(cell, width=d + 8, height=d + 8, bg=UI_HOVER, highlightthickness=0, bd=0)
                cv.pack()
                self.draw_ball(canvas=cv, tier=tier, r=d / 2, w=d + 8, zroom=4)
                tk.Label(cell, text=title, font=small, bg=UI_HOVER, fg=TX).pack()
                tk.Label(cell, text=self.BALL_TIERS[tier][1], font=("Malgun Gothic", 9, "bold"), bg=UI_HOVER,
                         fg=TX).pack()
            show(0, cur, "지금")
            if nxt is not None:
                tk.Label(row, text="▶", font=small, bg=UI_HOVER, fg=SUB).grid(row=0, column=1)
                show(2, nxt, f"Lv.{self.BALL_TIERS[nxt][0]} 에서")
            self.card_ball_note = tk.Label(box, font=small, bg=UI_HOVER, fg=SUB)
            self.card_ball_note.pack(pady=(6, 0))
            self.update_ball_note()
        self.place_status()

    def update_ball_note(self):
        if self.card_ball is None:
            return
        nxt = self.ball_tier() + 1
        if nxt >= len(self.BALL_TIERS):
            text = "이게 마지막 볼이에요!"
        else:
            need = (self.BALL_TIERS[nxt][0] - 1) * 10 - self.affection
            text = f"친밀도 {max(1, math.ceil(need))} 더 올리면 바뀌어요"
        self.card_ball_note.config(text=text)

    def place_status(self, resized=True):
        """나몰빼미 오른쪽에 (자리가 없으면 왼쪽에), 아랫변을 나몰빼미 발에 맞춰 띄움. 나몰빼미를 따라다님"""
        w = self.status_win
        if resized or self.card_size is None:
            w.update_idletasks()
            self.card_size = (w.winfo_reqwidth(), w.winfo_reqheight())
            self.card_pos = None
        cw, ch = self.card_size
        gap = int(8 * self.S)
        x = int(self.x + self.W + gap)
        if x + cw > self.mon_right:  # 지금 모니터 안에 들어오게
            x = int(self.x - cw - gap)
        x = max(self.mon_left, min(x, self.mon_right - cw))
        y = max(self.top, min(int(self.y + self.H - ch), self.bottom - ch))
        if (x, y) != self.card_pos:
            self.card_pos = (x, y)
            w.geometry(f"+{x}+{y}")

    @staticmethod
    def mouse_down():
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

    def update_status(self, now):
        """상태 카드가 떠 있으면: 1초마다 수치를 새로 그리고, 카드·나몰빼미 밖을 클릭하면 닫음"""
        if self.status_win is None:
            return
        down = self.mouse_down()
        px, py = self.root.winfo_pointerxy()
        w = self.status_win
        in_card = (w.winfo_rootx() <= px < w.winfo_rootx() + w.winfo_width()
                   and w.winfo_rooty() <= py < w.winfo_rooty() + w.winfo_height())
        if down and not self.card_mouse and not self.menu_open:
            in_pet = self.x <= px < self.x + self.W and self.y <= py < self.y + self.H
            if not in_card and not in_pet:
                self.card_mouse = down
                self.close_status()
                return
        self.card_mouse = down
        if now - self.card_drawn >= 1:
            self.refresh_status()
        # 나몰빼미를 따라가되, 마우스가 카드 위에 있거나 메뉴가 열려 있으면 버튼이 움직이지 않게 멈춤
        if self.status_win is not None and not in_card and not self.menu_open:
            self.place_status(resized=False)

    def refresh_status(self, force=False):
        if self.status_win is None:
            return
        self.card_drawn = time.time()
        self.card_lv.config(text=f"Lv.{self.level()} · {self.BALL_TIERS[self.ball_tier()][1]} ▾")
        self.update_ball_note()
        self.card_mood.config(text=self.status_summary())
        for key, (c, rect, val, color, bw, bh) in self.card_bars.items():
            if key == "affection":  # 다음 레벨까지 (10 마다 한 레벨)
                part = self.affection % 10
                frac, text, fill = part / 10, f"{int(part)}/10", color
            else:
                v = getattr(self, key)
                low = v <= (HUNGRY_AT if key == "full" else GRUMPY_AT)
                frac, text, fill = v / 100, str(int(v)), self.CARD_LOW if low else color
            c.coords(rect, 0, 0, round(bw * frac), bh)
            c.itemconfig(rect, fill=fill)
            val.config(text=text)
        self.card_btns[2].config(text="깨우기" if self.pomo_phase == "focus" else "재우기")
        lines = self.status_lines()
        if force or [l[:2] for l in lines] != [l[:2] for l in (self.card_lines or [])]:
            self.card_lines = lines
            for ch in self.card_info.winfo_children():
                ch.destroy()
            BG = self.CARD_BG
            for r, (name, text, action) in enumerate(lines):
                tk.Label(self.card_info, text=name, font=("Malgun Gothic", 9), bg=BG, fg=self.CARD_SUB,
                         anchor="w").grid(row=r, column=0, sticky="w", padx=(0, 10))
                v = tk.Label(self.card_info, text=text, font=("Malgun Gothic", 9), bg=BG, fg=self.CARD_TEXT,
                             anchor="w", justify="left")
                v.grid(row=r, column=1, sticky="w", pady=1)
                if action:
                    v.config(cursor="hand2")
                    v.bind("<Button-1>", lambda e, a=action: a())
                    v.bind("<Enter>", lambda e, v=v: v.config(fg=UI_SKY))
                    v.bind("<Leave>", lambda e, v=v: v.config(fg=self.CARD_TEXT))
            self.place_status()  # 줄 수나 길이가 바뀌면 크기가 바뀜

    def status_summary(self):
        if self.pomo_phase == "focus":
            return "쿨쿨 자는 중"
        if self.is_day_off(date.today()):
            return "쉬는 날 · 수치 그대로"
        if self.full <= HUNGRY_AT:
            return "배고파요"
        if self.mood <= GRUMPY_AT:
            return "심심해서 삐졌어요"
        if self.full >= 70 and self.mood >= 70:
            return "기분 최고예요"
        return "평온해요"

    def status_lines(self):
        """상태 카드의 오늘 정보: [(이름, 내용, 누르면 할 일)]"""
        lines = []
        if self.has_schedule_source:
            if self.today_data is None:
                lines.append(("다음 일정", "불러오는 중...", None))
            else:
                events, todos = self.today_data
                lines.append(("다음 일정", self.next_event_text(events), self.show_agenda))
                if todos is not None:
                    today = date.today().isoformat()
                    late = sum(1 for t in todos if t["due"] and t["due"] < today)
                    due = sum(1 for t in todos if t["due"] == today)
                    extra = ", ".join(s for s in (f"오늘 마감 {due}" if due else "",
                                                  f"기한 지남 {late}" if late else "") if s)
                    lines.append(("할 일", f"{len(todos)}개 남음" + (f" ({extra})" if extra else ""),
                                  self.todo_window if self.notion.connected else None))
        if self.pomo_phase:
            left = max(0, math.ceil((self.pomo_end - time.time()) / UNIT))
            lines.append(("재우기", f"자는 중 · {left}분 남음" if self.pomo_phase == "focus"
                          else f"쉬는 시간 · {left}분 남음", None))
        else:
            lines.append(("재우기", f"오늘 {self.pomo_today()}번 재웠어요", None))
        return lines

    @staticmethod
    def next_event_text(events):
        now = datetime.now()
        local = lambda t: datetime.fromisoformat(t).astimezone().replace(tzinfo=None)  # PC 시간대(서울)로
        tag = lambda ev: "[팀] " if ev.get("source") == "notion" else ""
        timed = []
        for ev in events:
            if not ev["all_day"]:
                s = local(ev["start"])
                e = local(ev["end"]) if ev["end"] else s
                if e > now:
                    timed.append((s, e, ev))
        if timed:
            s, e, ev = min(timed, key=lambda t: t[0])
            if s <= now:
                return f"지금 {tag(ev)}{ev['summary'][:18]} (~{e:%H:%M})"
            return f"{s:%H:%M} {tag(ev)}{ev['summary'][:18]}"
        all_day = [ev for ev in events if ev["all_day"]]
        if all_day:
            more = f" 외 {len(all_day) - 1}개" if len(all_day) > 1 else ""
            return f"하루 종일 {tag(all_day[0])}{all_day[0]['summary'][:16]}{more}"
        return "오늘 남은 일정이 없어요" if events else "오늘은 일정이 없어요"

    def toggle_pomo(self):
        if self.pomo_phase == "focus":
            self.pomo_stop()
        else:
            self.pomo_start()

    def pomo_today(self):
        return self.pomo_count if self.pomo_day == date.today().isoformat() else 0

    def target_item(self):
        return next((it for it in self.items if not it.dragging), None)

    def reach_item(self, it):
        self.start_visit(VISIT_PLAYED)  # 먹은 자리 주변에 잠시 있다가 볼로 돌아감
        it.remove()
        self.bowl_hide_at = time.time() + 1.9  # 다 먹으면 밥그릇이 사라짐 (먹는 시간 1.6초)
        self.set_state("eat", 1.6)
        if not self.gain(full=30, mood=5, affection=2):
            self.say(random.choice(["냠냠!", "맛있어요!", "열매 최고!"]), 1.6)
