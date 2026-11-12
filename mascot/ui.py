"""창 색감 테마, 날짜 고르기 위젯, 그림 부드럽게 줄이기(scaled_photo)"""

import calendar
import math
import tkinter as tk
from datetime import date, datetime


# ---------- 창 색감: 풀·비행 타입 (새잎 연두 바탕 + 숲 초록 + 하늘색) ----------
# 상태 카드·말풍선·메뉴·설정 창이 모두 이 색을 씀
UI_BG = "#e6ece0"      # 바탕 (차분한 세이지)
UI_FIELD = "#f1f4ec"   # 입력 칸·목록 바탕
UI_LINE = "#a7b99b"    # 테두리·구분선
UI_TEXT = "#1f3324"    # 글자 (짙은 숲색)
UI_SUB = "#566f59"     # 설명 글자
UI_HOVER = "#d6e0cc"   # 버튼 바탕
UI_PRESS = "#c3d2b6"   # 버튼 누를 때·메뉴 고를 때
UI_ACCENT = "#4b8455"  # 선택한 것·레벨 배지 (풀 타입 초록)
UI_SKY = "#6a97b8"     # 두 번째 강조색 (비행 타입 하늘색)
UI_TRACK = "#d0dbc6"   # 상태 카드 막대의 빈 부분
# 예전에 창마다 직접 넣어 둔 색 → 새 색
UI_REMAP = {"#666": UI_SUB, "#555": UI_SUB, "#222": UI_TEXT, "#ccc": UI_LINE, "#9aa4b2": UI_LINE,
            "white": UI_BG, "#4a90d9": UI_ACCENT, "#e8f0fe": UI_HOVER, "#cfe0fc": UI_PRESS,
            "#1a73e8": UI_SKY}


def theme_menu(m):
    m.config(bg=UI_BG, fg=UI_TEXT, activebackground=UI_PRESS, activeforeground=UI_TEXT,
             selectcolor=UI_ACCENT, relief="flat", bd=1, font=("Malgun Gothic", 10))
    return m


def apply_theme(w):
    """창 안의 모든 위젯에 같은 색감을 입힘 (창을 다 만든 뒤에 부름)"""
    cls = w.winfo_class()
    try:
        bg = str(w.cget("bg"))
    except tk.TclError:
        bg = ""
    is_default = bg.startswith("System") or bg in ("", "#f0f0f0")
    new_bg = UI_REMAP.get(bg, UI_BG if is_default else bg)
    if cls in ("Toplevel", "Tk", "Frame"):
        w.config(bg=new_bg)
    elif cls == "Label":
        fg = str(w.cget("fg"))
        w.config(bg=new_bg, fg=UI_REMAP.get(fg, UI_TEXT if fg.startswith("System") else fg))
    elif cls == "Button":
        fg = str(w.cget("fg"))
        fg = UI_REMAP.get(fg, UI_TEXT if fg.startswith("System") else fg)
        if is_default:  # 보통 버튼: 크림색 바탕 + 얇은 테두리
            w.config(bg=UI_HOVER, fg=fg, activebackground=UI_PRESS, activeforeground=UI_TEXT, relief="flat",
                     bd=0, highlightthickness=1, highlightbackground=UI_LINE, highlightcolor=UI_LINE,
                     padx=8, pady=2, cursor="hand2")
        else:  # 달력 날짜처럼 색을 정해 둔 버튼
            w.config(bg=new_bg, fg=fg, activebackground=UI_PRESS, cursor="hand2")
    elif cls == "Entry":
        w.config(bg=UI_FIELD, fg=UI_TEXT, readonlybackground=UI_BG, insertbackground=UI_TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=UI_LINE, highlightcolor=UI_ACCENT,
                 selectbackground=UI_ACCENT, selectforeground="white")
    elif cls == "Listbox":
        w.config(bg=UI_FIELD, fg=UI_TEXT, selectbackground=UI_ACCENT, selectforeground="white", relief="flat",
                 highlightthickness=1, highlightbackground=UI_LINE, highlightcolor=UI_LINE)
    elif cls in ("Checkbutton", "Radiobutton"):
        w.config(bg=UI_BG, fg=UI_TEXT, activebackground=UI_BG, activeforeground=UI_TEXT,
                 selectcolor=UI_FIELD, highlightthickness=0)
    elif cls == "Menubutton":  # 고르기 칸 (OptionMenu)
        w.config(bg=UI_HOVER, fg=UI_TEXT, activebackground=UI_PRESS, activeforeground=UI_TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=UI_LINE, cursor="hand2")
        theme_menu(w.nametowidget(w.cget("menu")))
    for ch in w.winfo_children():
        if ch.winfo_class() != "Menu":
            apply_theme(ch)


class DatePicker:
    """날짜 칸을 누르면 그 바로 아래에 뜨는 작은 달력. 날짜를 누르면 칸에 들어가고 닫힘"""
    current = None  # 한 번에 하나만 띄움

    def __init__(self, parent, entry, on_pick=None):
        if DatePicker.current is not None:
            DatePicker.current.close()
        DatePicker.current = self
        self.entry, self.on_pick = entry, on_pick
        try:
            self.sel = datetime.strptime(entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            self.sel = date.today()
        self.year, self.month = self.sel.year, self.sel.month
        w = self.win = tk.Toplevel(parent)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg="#9aa4b2")  # 얇은 테두리
        self.body = tk.Frame(w, bg="white", padx=6, pady=6)
        self.body.pack(padx=1, pady=1)
        entry.update_idletasks()
        w.geometry(f"+{entry.winfo_rootx()}+{entry.winfo_rooty() + entry.winfo_height() + 2}")
        w.bind("<Escape>", lambda e: self.close())
        self.render()
        w.focus_force()

    def render(self):
        for ch in self.body.winfo_children():
            ch.destroy()
        font = ("Malgun Gothic", 9)
        head = tk.Frame(self.body, bg="white")
        head.grid(row=0, column=0, columnspan=7, sticky="we", pady=(0, 4))
        tk.Button(head, text="◀", bd=0, bg="white", font=font, command=lambda: self.move(-1)).pack(side="left")
        tk.Label(head, text=f"{self.year}년 {self.month}월", bg="white",
                 font=("Malgun Gothic", 10, "bold")).pack(side="left", expand=True)
        tk.Button(head, text="✕", bd=0, bg="white", fg="#d93025", font=font, cursor="hand2",
                  command=self.close).pack(side="right", padx=(4, 0))
        tk.Button(head, text="▶", bd=0, bg="white", font=font, command=lambda: self.move(1)).pack(side="right")
        for i, name in enumerate("일월화수목금토"):
            fg = "#d93025" if i == 0 else ("#1a73e8" if i == 6 else "#555")
            tk.Label(self.body, text=name, bg="white", fg=fg, font=font, width=3).grid(row=1, column=i)
        today = date.today()
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(self.year, self.month)  # 일요일부터
        for r, week in enumerate(weeks, start=2):
            for c, d in enumerate(week):
                other = d.month != self.month
                fg = "#bbb" if other else ("#d93025" if c == 0 else ("#1a73e8" if c == 6 else "#222"))
                bg = "white"
                if d == self.sel:
                    bg, fg = "#4a90d9", "white"
                elif d == today:
                    bg = "#e8f0fe"
                tk.Button(self.body, text=str(d.day), width=3, bd=0, relief="flat", bg=bg, fg=fg,
                          activebackground="#cfe0fc", font=("Malgun Gothic", 9, "bold" if d == today else "normal"),
                          command=lambda d=d: self.pick(d)).grid(row=r, column=c, padx=1, pady=1)
        apply_theme(self.win)

    def move(self, step):
        m = self.month - 1 + step
        self.year, self.month = self.year + m // 12, m % 12 + 1
        self.render()

    def pick(self, d):
        self.entry.delete(0, "end")
        self.entry.insert(0, d.isoformat())
        if self.on_pick:
            self.on_pick(d)
        self.close()

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if DatePicker.current is self:
            DatePicker.current = None


def scaled_photo(src, scale):
    """PhotoImage 를 scale(<1) 배로 부드럽게 줄임 (Tk 의 subsample 은 픽셀을 건너뛰어 깨져 보여서, 칸 안 색을 평균)"""
    w, h = src.width(), src.height()
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    px = [[src.get(x, y) for x in range(w)] for y in range(h)]
    solid = [[not src.transparency_get(x, y) for x in range(w)] for y in range(h)]
    out = tk.PhotoImage(width=tw, height=th)
    for ty in range(th):
        y0, y1 = ty / scale, (ty + 1) / scale
        runs, cur, start = [], [], 0
        for tx in range(tw):
            x0, x1 = tx / scale, (tx + 1) / scale
            r = g = b = cover = 0.0
            for y in range(int(y0), min(h, math.ceil(y1))):
                wy = min(y + 1, y1) - max(y, y0)
                for x in range(int(x0), min(w, math.ceil(x1))):
                    if solid[y][x]:
                        wt = wy * (min(x + 1, x1) - max(x, x0))
                        p = px[y][x]
                        r += p[0] * wt
                        g += p[1] * wt
                        b += p[2] * wt
                        cover += wt
            if cover >= 0.5 * (x1 - x0) * (y1 - y0):
                if not cur:
                    start = tx
                cur.append("#%02x%02x%02x" % (round(r / cover), round(g / cover), round(b / cover)))
            elif cur:
                runs.append((start, cur))
                cur = []
        if cur:
            runs.append((start, cur))
        for sx, colors in runs:
            out.put("{" + " ".join(colors) + "}", to=(sx, ty))
    return out
