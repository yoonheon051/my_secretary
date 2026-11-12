"""Gmail·Slack 알림"""

import os
import queue
import time
import tkinter as tk
import webbrowser

from ..constants import MAIL_CFG, SLACK_MANIFEST, SLACK_TOKEN
from ..mail import MailChecker
from ..secrets_store import save_secret
from ..slack import SlackChecker
from ..ui import apply_theme
from ..winapi import bring_to_front, find_app_window


class NotificationsMixin:
    # ---------- Gmail ----------
    def start_mail(self, addr, password):
        self.stop_mail()
        self.mail_known = None
        self.mail = MailChecker(addr, password, self.mail_q)
        self.mail.start()

    def stop_mail(self):
        if self.mail:
            self.mail.stop_evt.set()
            self.mail = None
        self.has_letter = False
        self.brief = None

    # ---------- Slack 알림 ----------
    def start_slack(self, token):
        self.stop_slack()
        self.slack_err = None
        self.slack = SlackChecker(token, self.slack_q)
        self.slack.start()

    def stop_slack(self):
        if self.slack:
            self.slack.stop_evt.set()
            self.slack = None

    def slack_off(self):
        self.stop_slack()
        try:
            os.remove(SLACK_TOKEN)
        except OSError:
            pass
        self.say("Slack 알림을 껐어요.\n저장된 토큰도 지웠어요.", 3)

    def update_slack(self):
        try:
            kind, data = self.slack_q.get_nowait()
        except queue.Empty:
            return
        if kind == "ok":
            if self.slack_announce:
                self.slack_announce = False
                self.say(f"Slack 연결 완료! ({data['team']})\n멘션이나 DM이 오면 알려 드릴게요.", 6)
        elif kind == "err":
            if data != self.slack_err:  # 같은 오류를 1분마다 반복해서 말하지 않게
                self.slack_err = data
                hint = ("\n토큰이 만료됐거나 앱이 지워졌어요.\n설정에서 Slack 알림을 다시 설정해 주세요."
                        if data in ("invalid_auth", "token_revoked", "account_inactive", "not_authed") else "")
                self.say(f"Slack 을 확인하지 못했어요. ({data}){hint}", 8)
                if hint:
                    self.stop_slack()
        elif kind == "new":
            self.slack_err = None
            kinds = {k for k, *_ in data}
            head = (f"Slack {'DM' if kinds == {'DM'} else '멘션' if kinds == {'멘션'} else '멘션·DM'}"
                    f" {len(data)}개 왔어요!")
            # DM·멘션 모두 보낸 사람만 보여 줌 (화면을 보는 다른 사람에게 내용이 보이지 않게)
            lines = [head] + [f"· {who[:10]}" for _, who, _, _ in data[-3:]]
            lines.append("(누르면 Slack 을 열어요)")
            self.say("\n".join(lines), 12)
            self.slack_notice_until = time.time() + 12
            self.slack_open_to = data[-1][3]
            if self.state in ("idle", "walk", "sleep", "home") and self.pomo_phase != "focus":
                self.set_state("happy", 1.2)

    def open_slack(self):
        """Slack 데스크톱 앱에서 마지막으로 온 대화를 엶 (안 되면 Slack 창만 앞으로)"""
        self.slack_notice_until = 0.0
        self.hide_bubble()
        team = self.slack.team if self.slack else None
        if team and self.slack_open_to:
            try:
                os.startfile(f"slack://channel?team={team}&id={self.slack_open_to}")
                return
            except OSError:
                pass
        hwnd = find_app_window("slack.exe")
        if hwnd:
            bring_to_front(hwnd)
        else:
            self.say("Slack 앱을 찾지 못했어요.", 3)

    def slack_setup(self):
        """Slack 알림 설정: 앱 만들기 안내 + 사용자 토큰(xoxp-) 붙여넣기"""
        d = self.dialog = tk.Toplevel(self.root)
        d.title("Slack 알림 설정")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        f = tk.Frame(d, padx=16, pady=12)
        f.pack()
        font = ("Malgun Gothic", 10)
        tk.Label(f, font=font, justify="left", text=(
            "나를 멘션하거나 DM이 오면 알려 드리려면 Slack '사용자 토큰'이 필요해요. (읽기 전용)\n"
            "1. 아래 링크에서 Create New App → From a manifest → 내 워크스페이스 선택\n"
            "2. 'manifest 복사' 버튼으로 복사한 내용을 붙여넣고 Create\n"
            "3. Install to Workspace → 허용  (막혀 있으면 관리자 승인이 필요해요)\n"
            "4. OAuth & Permissions 의 'User OAuth Token' (xoxp-로 시작)을 아래에 붙여넣기")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        link = tk.Label(f, text="https://api.slack.com/apps", fg="#1a73e8", cursor="hand2", font=font)
        link.grid(row=1, column=0, sticky="w", pady=(4, 8))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://api.slack.com/apps"))

        def copy_manifest():
            try:
                with open(SLACK_MANIFEST, encoding="utf-8") as fp:
                    text = fp.read()
            except OSError:
                warn.config(text="slack_manifest.yaml 파일이 없어요.")
                return
            d.clipboard_clear()
            d.clipboard_append(text)
            warn.config(text="manifest 를 복사했어요. Slack 앱 만들기 화면에 붙여넣으세요.")

        tk.Button(f, text="manifest 복사", command=copy_manifest).grid(row=1, column=1, sticky="w", pady=(4, 8))
        tk.Label(f, text="사용자 토큰", font=font).grid(row=2, column=0, sticky="e", padx=(0, 8))
        tok = tk.Entry(f, width=46, font=font, show="•")
        tok.grid(row=2, column=1, columnspan=2, sticky="w", pady=3)
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666", justify="left",
                 text="토큰은 이 PC의 내 Windows 계정에서만 풀 수 있게 암호화해서 저장해요.\n"
                      "메시지는 읽기만 하고 읽음 처리하지 않아요.").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(8, 8))
        warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025", justify="left")
        warn.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

        def save():
            t = tok.get().strip()
            if not t.startswith("xoxp-"):
                warn.config(text="'User OAuth Token' 은 xoxp- 로 시작해요. (xoxb- 봇 토큰은 안 돼요)")
                return
            save_secret(SLACK_TOKEN, {"token": t})
            d.destroy()
            self.slack_announce = True
            self.say("Slack 에 연결해 볼게요...", 3)
            self.start_slack(t)

        btns = tk.Frame(f)
        btns.grid(row=4, column=0, columnspan=3, sticky="e")
        tk.Button(btns, text="저장", width=8, command=save).pack(side="left", padx=4)
        tk.Button(btns, text="취소", width=8, command=d.destroy).pack(side="left")
        tok.bind("<Return>", lambda e: save())
        apply_theme(d)
        tok.focus_set()

    def mail_off(self):
        self.stop_mail()
        try:
            os.remove(MAIL_CFG)
        except OSError:
            pass
        self.say("메일 알림을 껐어요.\n저장된 로그인 정보도 지웠어요.", 3)

    def update_mail(self):
        try:
            kind, data = self.mail_q.get_nowait()
        except queue.Empty:
            return
        if self.mail is None:
            return
        if kind == "auth":
            self.stop_mail()
            self.say("Gmail 로그인에 실패했어요.\n주소와 앱 비밀번호를 확인해 주세요.\n(우클릭 → 설정·기타 → 설정 → Gmail 알림 설정)", 8)
            return
        if kind != "ok":
            return  # 일시적인 네트워크 오류는 다음 확인 때 다시 시도
        uids, recent, brief = data
        if brief and brief[2] is not None:
            self.apply_vacations(brief[2], "mail")  # 메일에 적힌 내 연차를 휴일로 (이미 연 브리핑이어도)
        if brief and brief[0] != self.brief_seen and (self.brief is None or self.brief[0] != brief[0]):
            self.brief = brief  # 아직 안 연 새 오전 브리핑
            self.brief_since = time.time()
            if self.brief_auto_var.get():
                # 자리에 있으면 바로, 자리를 비웠으면 돌아와서 마우스·키보드를 건드릴 때 열림 (update_brief)
                self.say("오전 브리핑이 도착했어요!\n열어 드릴게요.", 6)
            else:
                self.say("오전 브리핑이 도착했어요!\n저를 클릭하면 열어 드릴게요.", 10)
            if self.state in ("idle", "walk", "sleep"):
                self.set_state("happy", 1.2)
        uids = set(uids)
        first = self.mail_known is None
        new = set() if first else uids - self.mail_known
        self.mail_known = uids
        self.mail_recent = recent
        if not uids:
            self.has_letter = False
            if first and not self.brief:  # 브리핑 도착 알림이 있으면 그걸 가리지 않게
                self.say("Gmail 연결 완료!\n새 메일이 오면 물어다 드릴게요.", 4)
            return
        if first:
            self.has_letter = True
            if not self.brief:  # 브리핑 알림이 먼저
                self.say(f"안 읽은 메일이 {len(uids)}통 있어요.\n저를 클릭해 보세요.", 4)
        elif new:
            self.has_letter = True
            who, subject = recent[0] if recent else ("", "")
            self.say(f"메일 왔어요!\n{who}\n「{subject[:40]}」", 7)
            if self.state in ("idle", "walk", "sleep"):
                self.set_state("happy", 1.0)

    @staticmethod
    def app_browser():
        """'앱 모드'(주소창·탭 없는 창)를 지원하는 브라우저 실행 파일: Chrome 먼저, 없으면 Edge"""
        import winreg
        for exe in ("chrome.exe", "msedge.exe"):
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                        path = winreg.QueryValue(k, None)
                    if path and os.path.exists(path):
                        return path
                except OSError:
                    continue
        return None

    def open_app_url(self, url):
        """브리핑·클로드 새 대화 열기. '전용 창'이 켜져 있으면 Chrome 앱 모드로 그 페이지만 띄우는 창을 엶
        (로그인은 Chrome 그대로)"""
        if self.brief_app_var.get():
            exe = self.app_browser()
            if exe:
                try:
                    import subprocess
                    subprocess.Popen([exe, f"--app={url}", "--window-size=980,900"])
                    return
                except OSError:
                    pass
        webbrowser.open(url)  # 끄거나 브라우저를 못 찾으면 평소 브라우저 탭으로

    def brief_click(self):
        uid, url = self.brief[:2]
        self.open_app_url(url)
        self.brief_seen, self.brief = uid, None
        self.last_brief_url = url
        self.save_pet()
        self.say("오전 브리핑을 열었어요!\n좋은 하루 보내요.", 4)

    def reopen_brief(self):
        if self.last_brief_url:
            self.open_app_url(self.last_brief_url)
            self.say("오전 브리핑을 다시 열었어요.", 3)
        else:
            self.say("아직 받은 오전 브리핑이 없어요.", 3)
