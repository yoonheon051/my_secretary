"""말풍선"""

import time
import tkinter as tk

from ..ui import UI_BG, UI_LINE, UI_TEXT
from ..winapi import bring_to_front, find_claude_window


class BubbleMixin:
    # ---------- 말풍선 ----------
    def build_bubble(self):
        b = self.bubble = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        b.configure(bg=UI_LINE)  # 1px 테두리 (상태 카드와 같은 색)
        self.blabel = tk.Label(b, font=("Malgun Gothic", 10), bg=UI_BG, fg=UI_TEXT,
                               padx=10, pady=6, justify="left", wraplength=int(260 * self.S))
        self.blabel.pack(padx=1, pady=1)
        self.blabel.bind("<Button-1>", lambda e: self.bubble_click())
        b.withdraw()
        self.bubble_until = 0.0

    def bubble_click(self):
        """말풍선 클릭: Claude·Slack 알림이면 그 창을 앞으로 띄우고, 아니면 그냥 닫기"""
        if time.time() < self.claude_notice_until:
            self.open_claude()
        elif time.time() < self.slack_notice_until:
            self.open_slack()
        else:
            self.hide_bubble()

    def open_claude(self):
        self.claude_notice_until = 0.0
        self.hide_bubble()
        try:
            hwnd = find_claude_window()
        except Exception:
            hwnd = None
        if hwnd:
            bring_to_front(hwnd)
        else:
            self.say("Claude 창을 찾지 못했어요.", 3)

    def say(self, text, secs=4):
        self.claude_notice_until = self.slack_notice_until = 0.0  # 다른 말을 하면 '알림 클릭' 은 끝
        self.blabel.config(text=text)
        self.bubble_until = time.time() + secs
        # 숨겼던 창을 다시 띄우면 위치가 (0, 0)으로 초기화될 수 있어서, 위치를 먼저 잡고 띄운 뒤 한 번 더 잡음
        self.bubble_pos = None
        self.place_bubble(time.time())
        self.bubble.deiconify()
        self.bubble.update_idletasks()
        self.bubble_pos = None
        self.place_bubble(time.time())
        self.restack()  # 말풍선을 나몰빼미보다 앞으로

    def hide_bubble(self):
        self.bubble_until = 0.0
        self.bubble.withdraw()
        self.bubble_pos = None

    def place_bubble(self, now):
        if not self.bubble_until:
            return
        if now >= self.bubble_until:
            self.hide_bubble()
            return
        bw, bh = self.blabel.winfo_reqwidth() + 2, self.blabel.winfo_reqheight() + 2
        bx = int(self.x + self.W / 2 - bw / 2)
        bx = max(self.mon_left, min(bx, self.mon_right - bw))  # 지금 모니터 안에
        by = int(self.y + self.sink_now + self.head - bh)  # 둥지에 앉아 가라앉은 만큼 머리도 낮아짐
        if self.state == "pet" or self.claude_busy:  # 쓰다듬는 손·고민 구름이 가려지지 않게 그 위로
            by -= int(self.head)
        if by < self.top:
            by = int(self.y + self.H)
        if self.in_ball:  # 볼 안에 있는 동안은 볼 위에 말풍선
            bx = max(self.mon_left, min(int(self.ball_cx - bw / 2), self.mon_right - bw))
            by = int(self.ball_cy - self.ball_r - self.ball_zroom - bh - 4 * self.S)
        if (bx, by) != self.bubble_pos:
            self.bubble_pos = (bx, by)
            self.bubble.geometry(f"+{bx}+{by}")
