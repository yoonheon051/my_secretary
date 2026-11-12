"""마우스 입력·메뉴"""

import math
import os
import random
import time
import tkinter as tk
import webbrowser
from datetime import date

from ..constants import (
    LINES,
    MAIL_CFG,
    SHUTDOWN_AFTER,
    SLACK_TOKEN,
    TICK_MS,
    WEATHER_PLACE,
    WORK_STRETCH_MIN,
)
from ..ui import theme_menu


class InputEventsMixin:
    # ---------- 입력 ----------
    def on_press(self, e):
        self.press = (e.x_root, e.y_root)
        self.grab = (e.x_root - self.x, e.y_root - self.y)
        self.trail = [(time.time(), self.x, self.y)]
        self.dragging = False

    def on_motion(self, e):
        if not self.dragging:
            if abs(e.x_root - self.press[0]) + abs(e.y_root - self.press[1]) < 5:
                return
            self.dragging = True
            self.set_state("drag")
            self.say("앗?!", 1.2)
        self.x = e.x_root - self.grab[0]
        self.y = e.y_root - self.grab[1]
        now = time.time()
        self.trail.append((now, self.x, self.y))
        self.trail = [p for p in self.trail if now - p[0] < 0.1] or self.trail[-1:]

    def on_release(self, e):
        if not self.dragging:
            self.on_click()
            return
        self.dragging = False
        t0, x0, y0 = self.trail[0]
        t1, x1, y1 = self.trail[-1]
        dt = max(t1 - t0, 0.016)
        lim = 40 * self.S
        self.vx = max(-lim, min(lim, (x1 - x0) / dt * TICK_MS / 1000))
        self.vy = max(-lim, min(lim, (y1 - y0) / dt * TICK_MS / 1000))
        self.thrown = True
        self.set_state("hover")  # 툭 떨어지지 않고 날개를 파닥이며 내려앉음

    def on_click(self):
        if time.time() < self.claude_notice_until:  # Claude 알림이 떠 있으면 Claude 창 띄우기
            self.open_claude()
        elif time.time() < self.slack_notice_until:  # Slack 알림이 떠 있으면 Slack 열기
            self.open_slack()
        elif self.brief:
            self.brief_click()
        elif self.report_url:  # 일일 업무 알림 뒤: Notion 일일보고 열기
            webbrowser.open(self.report_url)
            self.report_url = None
            self.say("일일 업무를 열었어요! 오늘도 수고했어요.", 4)
        elif self.has_letter:
            self.letter_click()
        elif self.pomo_phase == "focus":
            left = max(0, int(self.pomo_end - time.time()))
            amount = max(1, math.ceil(left / 60))  # 1분 안 남았어도 '1분'으로
            self.say(f"쿨쿨... {amount}분 뒤에 일어날게요.", 3)
        elif self.state == "sleep":
            self.set_state("idle", 2)
            if self.has_schedule_source and self.agenda_date != date.today().isoformat():
                self.show_agenda()  # 그날 첫 클릭이면 깨면서 오늘 일정부터
            else:
                self.say("음... 깼어요!", 2)
        elif self.has_schedule_source and self.agenda_date != date.today().isoformat():
            self.show_agenda()  # 그날 처음 클릭하면 오늘 일정부터
        else:
            # 쓰다듬기
            leveled = self.gain(mood=4, affection=0.5)
            if leveled:
                return
            if self.full < 30:
                self.say("쓰다듬어 줘서 좋은데... 배고파요.", 3)
            elif self.mood > 70 and random.random() < 0.5:
                self.say(random.choice(["헤헤, 좋아요!", "기분 좋아요~♥", "더 쓰다듬어 주세요!"]), 2)
                if self.state in ("idle", "walk", "sleep", "home"):
                    self.set_state("happy", 1.2)  # 기분 좋으면 신나는 포즈
            else:
                self.say(random.choice(LINES), 3)

    def on_menu(self, e):
        """우클릭: 상태 카드를 열고 닫음. 나머지 메뉴는 카드의 '일정·업무', '설정·기타' 버튼에서"""
        self.show_status()

    def schedule_menu(self):
        """상태 카드 '일정·업무' 버튼: 일정·할 일 (Google 캘린더 + Notion 팀 일정), 브리핑, 날씨,
        할 일 빠른 추가, 클로드에게 묻기"""
        m = tk.Menu(self.root, tearoff=0)
        if self.has_schedule_source:
            m.add_command(label="오늘 일정 보기", command=self.show_agenda)
            m.add_command(label="내 일정 (Google·Notion 팀 일정)...", command=self.schedule_window)
        if self.notion.connected:
            m.add_command(label="내 할 일 (Notion TODO)...", command=self.todo_window)
        m.add_command(label="오전 브리핑 다시 열기", command=self.reopen_brief)
        m.add_command(label=f"퇴근길 날씨 지금 보기 ({WEATHER_PLACE})", command=self.fetch_weather)
        m.add_separator()
        if self.notion.connected:
            m.add_command(label="할 일 빠르게 추가  (Ctrl+Alt+N)", command=self.quick_todo)
            m.add_command(label="일일 업무 쓰기  (Ctrl+Alt+D)", command=self.daily_report)
        m.add_command(label="클로드에게 묻기  (Ctrl+Alt+K)", command=self.ask_claude)
        m.add_command(label="숨기기·보이기  (Ctrl+Alt+H)", command=self.toggle_hidden)
        return m

    def more_menu(self):
        """상태 카드 '설정·기타' 버튼: 설정(하위 메뉴), 날아다니기, 집으로 돌아가기, 종료"""
        m = tk.Menu(self.root, tearoff=0)
        s = tk.Menu(m, tearoff=0)
        s.add_checkbutton(label="자유롭게 돌아다니기 (끄면 집 근처에서만)", variable=self.roam_var)
        if len(self.monitors) > 1:
            s.add_checkbutton(label="가끔 다른 모니터로 놀러 가기", variable=self.wander_var)
        s.add_checkbutton(label="열린 창 위에 올라가기", variable=self.perch_var)
        s.add_checkbutton(label=f"{WORK_STRETCH_MIN}분 넘게 쉬지 않으면 스트레칭 알림", variable=self.stretch_var)
        s.add_checkbutton(label=f"{SHUTDOWN_AFTER} 이후 자리를 비우면 PC 자동 종료", variable=self.shutdown_var,
                          command=self.shutdown_toggled)
        s.add_separator()
        s.add_checkbutton(label="오전 브리핑 자동으로 열기", variable=self.brief_auto_var,
                          command=self.save_pet)
        s.add_checkbutton(label="브리핑을 전용 창으로 열기 (끄면 브라우저 탭)", variable=self.brief_app_var,
                          command=self.save_pet)
        s.add_separator()
        if self.gcal.connected:
            s.add_command(label="Google 캘린더 연결 끊기", command=self.gcal_disconnect)
        else:
            s.add_command(label="Google 캘린더 연결...", command=self.gcal_connect)
        if self.notion.connected:
            s.add_command(label="Notion 연결 끊기", command=self.notion_disconnect)
        else:
            s.add_command(label="Notion 연결...", command=self.notion_setup)
        s.add_command(label="Gmail 알림 설정...", command=self.mail_setup)
        if self.slack or os.path.exists(SLACK_TOKEN):
            s.add_command(label="Slack 알림 끄기", command=self.slack_off)
        else:
            s.add_command(label="Slack 알림 설정...", command=self.slack_setup)
        if self.mail or os.path.exists(MAIL_CFG):
            s.add_command(label="Gmail 알림 끄기", command=self.mail_off)
        m.add_cascade(label="설정", menu=s)
        m.add_separator()
        m.add_command(label="날아다니기", command=self.start_fly)
        if len(self.monitors) > 1:
            m.add_command(label="다른 모니터로 놀러 가기", command=lambda: self.visit_other_monitor(announce=True))
        m.add_command(label="집으로 돌아가기", command=self.fly_home)
        m.add_separator()
        m.add_command(label="종료", command=self.quit)
        return m

    def popup_menu(self, m, x, y):
        for sub in [m] + [ch for ch in m.winfo_children() if ch.winfo_class() == "Menu"]:
            theme_menu(sub)  # 상태 카드와 같은 색감 (하위 메뉴 '설정'까지)
        self.menu_open = True
        try:
            m.tk_popup(x, y)  # 메뉴가 닫힐 때까지 기다림
        finally:
            m.grab_release()
            self.menu_open = False
            self.restack()
