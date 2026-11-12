"""퇴근 후 자동 종료"""

import time
import tkinter as tk
import webbrowser
from datetime import date, datetime

from ..constants import (
    APP_PASSWORD_URL,
    GMAIL_URL,
    SHUTDOWN_AFTER,
    SHUTDOWN_IDLE_MIN,
    SHUTDOWN_WARN_SEC,
)
from ..secrets_store import load_mail_cfg, save_mail_cfg
from ..ui import apply_theme
from ..winapi import idle_seconds


class AutoShutdownMixin:
    # ---------- 퇴근 후 자동 종료 ----------
    def update_shutdown(self, now):
        """규칙 하나: SHUTDOWN_AFTER 이후 마우스·키보드 입력이 SHUTDOWN_IDLE_MIN 분 동안 없으면
        SHUTDOWN_WARN_SEC 초 예고 뒤 PC 종료. 그 사이 아무거나 건드리면 취소 (나몰빼미를 누르는 것도 입력).
        Claude 작업 중(또는 재우기 중)에는 조용히 기다렸다가, 끝나면 다시 같은 규칙으로"""
        if now - self.last_shutdown_check < 1:
            return
        self.last_shutdown_check = now
        after = datetime.strptime(SHUTDOWN_AFTER, "%H:%M").time()
        wait = self.claude_busy or self.pomo_phase == "focus"
        if (not self.shutdown_var.get() or datetime.now().time() < after or wait
                or self.shutdown_done == date.today().isoformat()):
            if self.shutdown_at is not None:
                self.shutdown_at = None
                if wait:
                    self.say("클로드가 일하는 중이라\n끝날 때까지 기다릴게요.", 4)
            return
        idle = idle_seconds()
        if self.shutdown_at is None:
            if idle >= SHUTDOWN_IDLE_MIN * 60:
                self.shutdown_at = now + SHUTDOWN_WARN_SEC
                self.shutdown_warned = now
                self.say_shutdown(now)
            return
        if idle < now - self.shutdown_warned - 1:  # 예고한 뒤에 마우스·키보드를 건드림 → 자리에 있음
            self.shutdown_at = None
            self.say("자리에 계시네요! PC는 그대로 둘게요.", 4)
            return
        if now >= self.shutdown_at:
            self.shutdown_at = None
            self.shutdown_pc()
        elif int(self.shutdown_at - now) % 30 == 0:
            self.say_shutdown(now)  # 30초마다 남은 시간을 다시 알려 줌

    def say_shutdown(self, now):
        left = max(0, round(self.shutdown_at - now))
        when = f"{left // 60}분 {left % 60}초" if left >= 60 else f"{left}초"
        self.say(f"퇴근 시간이에요! {when} 뒤에 PC를 끌게요.\n"
                 "(마우스나 키보드를 건드리면 취소돼요)", SHUTDOWN_WARN_SEC + 5)
        if self.state in ("idle", "walk", "sleep", "home"):
            self.set_state("happy", 1.2)

    def shutdown_toggled(self):
        self.save_pet()
        if not self.shutdown_var.get():
            self.shutdown_at = None
        self.say(f"{SHUTDOWN_AFTER} 이후 자동 종료를 " + ("켰어요." if self.shutdown_var.get() else "껐어요."), 3)

    def shutdown_pc(self):
        """완전 종료 (빠른 시작용 최대 절전 없이). 강제 종료(/f)는 안 써서, 저장 안 한 문서가 있으면 Windows 가 물어봄"""
        self.save_pet()
        self.shutdown_done = date.today().isoformat()  # 한 번 보냈으면 (Windows 에서 취소했더라도) 오늘은 다시 안 함
        self.ball_hold_until = time.time() + 120  # 꺼질 때까지 볼 안에 있음 (Windows 에서 취소하면 2분 뒤에 나옴)
        self.say("오늘도 수고했어요!", 10)
        import subprocess
        try:
            subprocess.Popen(["shutdown", "/s", "/t", "3", "/c", "퇴근 시간이라 PC를 끕니다."],
                             creationflags=0x08000000)  # CREATE_NO_WINDOW
        except OSError as e:
            self.say(f"PC를 끄지 못했어요.\n{str(e)[:60]}", 6)

    BRIEF_PRESENT_SEC = 30  # 이 시간 안에 마우스·키보드를 건드렸으면 자리에 있는 것으로 봄

    def update_brief(self):
        """자동 열기: 브리핑이 와 있고 사용자가 자리에 있으면 바로 열기"""
        if (self.brief and self.brief_auto_var.get() and self.crossed(10)
                and time.time() - self.brief_since > 2.5  # '도착했어요' 말풍선을 잠깐 보여 준 뒤
                and idle_seconds() < self.BRIEF_PRESENT_SEC):
            self.brief_click()

    def letter_click(self):
        now = time.time()
        if now < self.letter_click_until:
            self.letter_click_until = 0.0
            self.has_letter = False
            webbrowser.open(GMAIL_URL)
            self.say("Gmail을 열었어요!", 2)
            return
        lines = [f"안 읽은 메일 {len(self.mail_known or [])}통"]
        for who, subject in self.mail_recent:
            lines.append(f"· {who[:16]}: {subject[:24]}")
        lines.append("(한 번 더 클릭하면 Gmail을 열어요)")
        self.letter_click_until = now + 6
        self.say("\n".join(lines), 6)

    def mail_setup(self):
        d = self.dialog = tk.Toplevel(self.root)
        d.title("Gmail 알림 설정")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        f = tk.Frame(d, padx=16, pady=12)
        f.pack()
        font = ("Malgun Gothic", 10)
        tk.Label(f, font=font, justify="left", text=(
            "Gmail 계정의 '앱 비밀번호'가 필요해요. (일반 비밀번호는 안 돼요)\n"
            "1. Google 계정에서 2단계 인증을 켭니다.\n"
            "2. 아래 링크에서 앱 비밀번호(16자리)를 만들어 붙여넣습니다.\n"
            "회사 계정은 관리자가 막아 두었을 수 있어요.")).grid(row=0, column=0, columnspan=2, sticky="w")
        link = tk.Label(f, text=APP_PASSWORD_URL, fg="#1a73e8", cursor="hand2", font=font)
        link.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))
        link.bind("<Button-1>", lambda e: webbrowser.open(APP_PASSWORD_URL))
        tk.Label(f, text="Gmail 주소", font=font).grid(row=2, column=0, sticky="e", padx=(0, 8))
        tk.Label(f, text="앱 비밀번호", font=font).grid(row=3, column=0, sticky="e", padx=(0, 8))
        addr = tk.Entry(f, width=34, font=font)
        pw = tk.Entry(f, width=34, font=font, show="•")
        addr.grid(row=2, column=1, pady=3)
        pw.grid(row=3, column=1, pady=3)
        cur = load_mail_cfg()
        if cur:
            addr.insert(0, cur[0])
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666", justify="left",
                 text="입력한 정보는 이 PC의 내 Windows 계정에서만 풀 수 있게 암호화해서 저장해요.\n"
                      "메일은 읽음 처리하지 않고, 안 읽은 메일의 보낸 사람과 제목만 확인해요.").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 8))

        warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025", justify="left")
        warn.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def save():
            a, p = addr.get().strip(), pw.get().strip()
            if not a or not p:
                return
            compact = p.replace(" ", "")
            if not (len(compact) == 16 and compact.isascii() and compact.isalpha()):
                warn.config(text="앱 비밀번호는 영문 16자예요 (예: abcd efgh ijkl mnop).\n"
                                 "평소 쓰는 Google 비밀번호로는 로그인할 수 없어요.")
                return
            save_mail_cfg(a, p)
            self.start_mail(a, p)
            d.destroy()
            self.say("Gmail에 연결해 볼게요...", 3)

        btns = tk.Frame(f)
        btns.grid(row=5, column=0, columnspan=2, sticky="e")
        tk.Button(btns, text="저장", width=8, command=save).pack(side="left", padx=4)
        tk.Button(btns, text="취소", width=8, command=d.destroy).pack(side="left")
        pw.bind("<Return>", lambda e: save())
        apply_theme(d)
        (pw if cur else addr).focus_set()

    def quit(self):
        self.save_pet()
        self.stop_mail()
        self.stop_slack()
        self.root.destroy()
