"""단축키: 할 일 빠른 추가·클로드에게 묻기"""

import queue
import tkinter as tk
from datetime import date, datetime, timedelta

from ..constants import NOTION_TODO_CATEGORIES
from ..ui import DatePicker, apply_theme


class QuickActionsMixin:
    # ---------- 단축키: 할 일 빠른 추가 / 클로드에게 묻기 ----------
    def update_hotkeys(self):
        try:
            name = self.hotkey_q.get_nowait()
        except queue.Empty:
            return
        getattr(self, name)()

    @staticmethod
    def clip_text(root, limit):
        """클립보드의 글 (없거나 글이 아니면 '')"""
        try:
            return root.clipboard_get().strip()[:limit]
        except tk.TclError:
            return ""

    def tool_window(self, title):
        """단축키로 여는 작은 창: 마우스 근처에 맨 앞으로 띄우고 입력할 수 있게 포커스를 가져옴"""
        d = self.dialog = tk.Toplevel(self.root)
        d.title(title)
        d.attributes("-topmost", True)
        d.resizable(False, False)
        px, py = self.root.winfo_pointerxy()
        d.mon = self.monitor_at(px)  # 마우스가 있는 모니터 안에 띄움
        d.geometry(f"+{max(d.mon[0], px - 200)}+{max(d.mon[1], py - 60)}")
        d.bind("<Escape>", lambda e: d.destroy())
        return d

    def show_tool_window(self, d, focus):
        apply_theme(d)
        d.update_idletasks()
        w, h = d.winfo_reqwidth(), d.winfo_reqheight()
        l, t, r, b = d.mon
        x = min(max(l, d.winfo_x()), r - w)
        y = min(max(t, d.winfo_y()), b - h)
        d.geometry(f"+{x}+{y}")
        d.lift()
        d.focus_force()  # 다른 프로그램을 쓰다가 단축키를 눌러도 바로 입력할 수 있게
        focus.focus_set()

    def quick_todo(self):
        """Ctrl+Alt+N: 할 일 빠른 추가. 복사해 둔 글이 있으면 미리 채워 둠"""
        if not self.notion.connected:
            self.say("Notion 이 연결돼 있어야 할 일을 넣을 수 있어요.", 4)
            return
        d = self.tool_window("할 일 빠른 추가 - Notion TODO")
        f = tk.Frame(d, padx=14, pady=12)
        f.pack()
        font = ("Malgun Gothic", 10)
        tk.Label(f, text="할 일", font=font).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=3)
        title = tk.Entry(f, width=40, font=font)
        title.grid(row=0, column=1, columnspan=3, sticky="w", pady=3)
        clip = " ".join(self.clip_text(self.root, 300).split())  # 여러 줄이면 한 줄로
        if clip:
            title.insert(0, clip[:120])
            title.select_range(0, "end")
        tk.Label(f, text="기한", font=font).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        due = tk.Entry(f, width=11, font=font, cursor="hand2")
        due.grid(row=1, column=1, sticky="w", pady=3)
        due.bind("<Button-1>", lambda e: (d.after(1, lambda: DatePicker(d, due)), "break")[1])

        def set_due(days):
            due.delete(0, "end")
            due.insert(0, (date.today() + timedelta(days=days)).isoformat())

        quick = tk.Frame(f)
        quick.grid(row=1, column=2, sticky="w", padx=(6, 0))
        tk.Button(quick, text="오늘", command=lambda: set_due(0)).pack(side="left", padx=(0, 3))
        tk.Button(quick, text="내일", command=lambda: set_due(1)).pack(side="left", padx=(0, 3))
        tk.Button(quick, text="지우기", command=lambda: due.delete(0, "end")).pack(side="left")
        tk.Label(f, text="분류", font=font).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        cat = tk.StringVar(value="(없음)")
        tk.OptionMenu(f, cat, "(없음)", *NOTION_TODO_CATEGORIES).grid(row=2, column=1, sticky="w", pady=3)
        warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025")
        warn.grid(row=3, column=0, columnspan=3, sticky="w")

        def submit():
            t = title.get().strip()
            if not t:
                warn.config(text="할 일을 입력해 주세요.")
                return
            dv = None
            if due.get().strip():
                try:
                    dv = datetime.strptime(due.get().strip(), "%Y-%m-%d").date()
                except ValueError:
                    warn.config(text="기한은 2026-10-22 처럼 적거나 달력에서 골라 주세요.")
                    return
            d.destroy()
            self.say("Notion 에 넣는 중...", 3)
            self.gcal_run("todo_add", self.notion.add_todo, t, dv, None if cat.get() == "(없음)" else cat.get())

        tk.Button(f, text="추가", width=8, command=submit).grid(row=3, column=3, sticky="e", pady=(6, 0))
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666",
                 text="Enter: 추가 · Esc: 닫기 · 복사해 둔 글이 있으면 미리 채워져요").grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))
        title.bind("<Return>", lambda e: submit())
        self.show_tool_window(d, title)
