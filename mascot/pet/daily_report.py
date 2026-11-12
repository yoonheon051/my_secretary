"""일일 업무 창"""

import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

from ..constants import CLAUDE_NEW_CHAT, FOCUS_MIN, UNIT
from ..ui import UI_ACCENT, UI_FIELD, UI_LINE, UI_TEXT, apply_theme


class DailyReportMixin:
    # ---------- 일일 업무 창 (Notion 을 열지 않고 메모장처럼 쓰고 저장·마감) ----------
    def daily_report(self):
        """Ctrl+Alt+D: 오늘 내 일일 업무를 메모장처럼 바로 쓰고 저장"""
        if not self.notion.connected:
            self.say("Notion 이 연결돼 있어야 일일 업무를 쓸 수 있어요.", 4)
            return
        if self.rep_win is not None and self.rep_win.winfo_exists():
            self.rep_win.lift()
            self.rep_win.focus_force()
            self.rep_text.focus_set()
            return
        d = self.dialog = self.rep_win = tk.Toplevel(self.root)
        d.title("일일 업무 - Notion")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        f = tk.Frame(d, padx=14, pady=12)
        f.pack()
        font = ("Malgun Gothic", 10)
        self.rep_title = tk.Label(f, text="오늘 일일 업무", font=("Malgun Gothic", 10, "bold"))
        self.rep_title.grid(row=0, column=0, columnspan=3, sticky="w")
        box = tk.Frame(f)
        box.grid(row=1, column=0, columnspan=3, sticky="we", pady=(4, 4))
        self.rep_text = tk.Text(box, width=62, height=15, font=font, wrap="word", undo=True, relief="flat",
                                bg=UI_FIELD, fg=UI_TEXT, insertbackground=UI_TEXT, highlightthickness=1,
                                highlightbackground=UI_LINE, highlightcolor=UI_ACCENT, padx=8, pady=6,
                                selectbackground=UI_ACCENT, selectforeground="white", spacing1=2, spacing3=2)
        sb = tk.Scrollbar(box, command=self.rep_text.yview)
        self.rep_text.config(yscrollcommand=sb.set)
        self.rep_text.tag_config("head", foreground=UI_ACCENT, font=("Malgun Gothic", 10, "bold"), spacing1=8)
        self.rep_text.config(width=40)  # 폭은 아래 버튼·안내 줄에 맞춰 늘어남
        sb.pack(side="right", fill="y")
        self.rep_text.pack(side="left", fill="both", expand=True)
        self.rep_text.bind("<Control-s>", lambda e: (self.report_save(), "break")[-1])
        self.rep_status = tk.Label(f, font=("Malgun Gothic", 9), fg="#666")
        self.rep_status.grid(row=2, column=0, sticky="w")
        btns = tk.Frame(f)
        btns.grid(row=2, column=1, columnspan=2, sticky="e")
        self.rep_save_btn = tk.Button(btns, text="저장 (Ctrl+S)", width=12, command=self.report_save)
        self.rep_save_btn.pack(side="left", padx=2)
        tk.Button(btns, text="새로고침", command=self.report_reload).pack(side="left", padx=2)
        self.rep_done_btn = tk.Button(btns, text="마감 (Done)", command=self.report_toggle_done)
        self.rep_done_btn.pack(side="left", padx=2)
        tk.Button(btns, text="Notion 에서 열기", command=lambda: self.rep_url and webbrowser.open(self.rep_url)).pack(
            side="left", padx=2)
        self.rep_warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025")
        self.rep_warn.grid(row=3, column=0, columnspan=3, sticky="w")
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666",
                 text="메모장처럼 쓰세요: Enter 로 새 줄 · 줄 하나가 Notion 글머리 하나 · ■ 칸 제목 줄은 지우지 마세요").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))
        self.rep_data, self.rep_url, self.rep_carried = None, None, False
        apply_theme(d)
        d.focus_force()
        self.rep_text.focus_set()
        self.refresh_report()

    def report_alive(self):
        return self.rep_win is not None and self.rep_win.winfo_exists()

    def refresh_report(self):
        if self.report_alive():
            self.rep_status.config(text="불러오는 중...")
            self.gcal_run("report_view", self.notion.read_report)

    def report_dirty(self):
        return self.report_alive() and bool(self.rep_text.edit_modified())

    def report_reload(self):
        if self.report_dirty():
            from tkinter import messagebox
            if not messagebox.askyesno("새로고침", "저장하지 않은 내용이 사라져요. 그래도 새로 불러올까요?", parent=self.rep_win):
                return
        self.refresh_report()

    def show_report(self, data, err=None):
        if not self.report_alive():
            return
        if err:
            self.rep_status.config(text=f"불러오지 못했어요: {str(err)[:60]}")
            return
        self.rep_data = data
        T = self.rep_text
        T.config(state="normal")
        T.delete("1.0", "end")
        if not data["exists"]:
            T.insert("end", "오늘 일일 업무 칸이 아직 없어요 (휴일이거나 아직 안 만들어졌어요).")
            T.config(state="disabled")
            self.rep_url = None
            self.rep_status.config(text="")
            self.rep_save_btn.config(state="disabled")
            return
        self.rep_save_btn.config(state="normal")
        self.rep_url = data["url"]
        carried = False
        for s, name in enumerate(self.notion.REPORT_SECTIONS):
            T.insert("end", f"■ {name}\n", "head")
            lines = [b["text"] for b in data["sections"][s]]
            while len(lines) > 1 and not lines[-1]:
                lines.pop()
            if s == 0 and data.get("carry") and not self.rep_carried:
                lines, carried = list(data["carry"]), True  # 지난 '익일 업무 계획' 미리 채움 (저장 전엔 Notion 에 안 올라감)
            T.insert("end", "\n".join(lines) + "\n")
        T.delete("end-1c", "end")
        T.edit_reset()
        T.edit_modified(carried)
        if carried:
            self.rep_carried = True
        done = data["status"] == "Done"
        self.rep_done_btn.config(text="마감 취소" if done else "마감 (Done)")
        self.rep_title.config(text=f"오늘 일일 업무 · {'마감함 ✔' if done else data['status'] or '작성 중'}")
        self.rep_status.config(text="지난 '익일 업무 계획'을 채웠어요 · 저장해야 올라가요" if carried
                               else f"{datetime.now():%H:%M} 기준")
        self.rep_warn.config(text="")

    def report_parse(self):
        """메모장 글을 칸별 줄 목록으로. 칸 제목이 없어졌으면 None"""
        names = self.notion.REPORT_SECTIONS
        out, cur = [[], [], []], None
        seen = []
        for line in self.rep_text.get("1.0", "end-1c").split("\n"):
            s = line.strip()
            if s.startswith("■"):
                num = s[1:].strip()[:1]
                if num in ("1", "2", "3"):
                    cur = int(num) - 1
                    seen.append(cur)
                    continue
            if cur is None:
                if s:
                    return None
                continue
            if s:
                out[cur].append(s.lstrip("•").strip() if s.startswith("•") else s)
        return out if seen == [0, 1, 2] else None

    def report_save(self):
        if not self.report_alive() or not self.rep_data or not self.rep_data.get("exists"):
            return
        texts = self.report_parse()
        if texts is None:
            self.rep_warn.config(text="■ 1. / ■ 2. / ■ 3. 칸 제목 줄이 있어야 저장돼요. (Ctrl+Z 로 되돌릴 수 있어요)")
            return
        self.rep_warn.config(text="")
        self.rep_status.config(text="Notion 에 저장하는 중...")
        self.rep_text.config(state="disabled")
        self.rep_save_btn.config(state="disabled")
        self.gcal_run("report_edit", self.notion.save_report, texts)

    def report_toggle_done(self):
        if self.report_dirty():
            self.rep_warn.config(text="먼저 저장해 주세요 (Ctrl+S).")
            return
        done = bool(self.rep_data and self.rep_data["status"] == "Done")
        self.rep_status.config(text="바꾸는 중...")
        self.gcal_run("report_edit", self.notion.set_report_status, "In progress" if done else "Done")

    def ask_claude(self):
        """Ctrl+Alt+K: 짧게 적은 질문(+ 복사해 둔 글)을 Claude 새 대화로 넘김"""
        d = self.tool_window("클로드에게 묻기")
        f = tk.Frame(d, padx=14, pady=12)
        f.pack()
        tk.Label(f, text="무엇을 물어볼까요?", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=0, sticky="w")
        box = tk.Text(f, width=50, height=5, font=("Malgun Gothic", 10), wrap="word", relief="flat",
                      bg=UI_FIELD, fg=UI_TEXT, insertbackground=UI_TEXT, highlightthickness=1,
                      highlightbackground=UI_LINE, highlightcolor=UI_ACCENT, padx=6, pady=4,
                      selectbackground=UI_ACCENT, selectforeground="white")
        box.grid(row=1, column=0, columnspan=2, pady=(4, 6))
        clip = self.clip_text(self.root, 5000)
        attach = tk.BooleanVar(value=bool(clip))
        if clip:
            preview = " ".join(clip.split())[:40] + ("…" if len(clip) > 40 else "")
            tk.Checkbutton(f, text=f"복사한 글 같이 보내기: {preview}", variable=attach,
                           font=("Malgun Gothic", 9)).grid(row=2, column=0, columnspan=2, sticky="w")

        def send():
            q = box.get("1.0", "end").strip()
            if attach.get() and clip:
                q = f"{q}\n\n---\n{clip}" if q else clip
            if not q:
                return
            d.destroy()
            self.open_app_url(CLAUDE_NEW_CHAT + urllib.parse.quote(q[:6000]))
            self.say("클로드에게 물어봤어요!", 3)

        tk.Button(f, text="보내기", width=8, command=send).grid(row=3, column=1, sticky="e", pady=(6, 0))
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666", text="Ctrl+Enter: 보내기 · Esc: 닫기").grid(
            row=3, column=0, sticky="w", pady=(6, 0))
        box.bind("<Control-Return>", lambda e: (send(), "break")[1])
        self.show_tool_window(d, box)

    def pomo_start(self):
        self.pomo_phase = "focus"
        self.pomo_end = time.time() + FOCUS_MIN * UNIT
        self.say("전 좀 잘게요", 4)  # 몬스터볼로 가는 건 update_ball 이 함

    def pomo_stop(self):
        self.pomo_phase = None
        self.say("음... 깼어요!", 3)
