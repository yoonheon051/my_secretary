"""Notion 연결과 내 할 일 창"""

import re
import tkinter as tk
import webbrowser
from datetime import date, datetime, timedelta

from ..constants import (
    FULL_DECAY,
    MOOD_DECAY,
    NOTION_PAGE_NAME,
    NOTION_REDIRECT,
    NOTION_TODO_CATEGORIES,
    UNIT,
    WHINE_MIN,
)
from ..ui import (
    DatePicker,
    UI_FIELD,
    UI_LINE,
    UI_SKY,
    UI_SUB,
    UI_TEXT,
    UI_TRACK,
    apply_theme,
)


class NotionUiMixin:
    # ---------- Notion ----------
    def notion_setup(self):
        """Notion 연결 창: OAuth 클라이언트 ID·시크릿을 넣고 '연결' → 브라우저에서 허용"""
        d = self.dialog = tk.Toplevel(self.root)
        d.title("Notion 연결")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        f = tk.Frame(d, padx=16, pady=12)
        f.pack()
        font = ("Malgun Gothic", 10)
        tk.Label(f, font=font, justify="left", text=(
            "Notion 통합(OAuth) 설정 화면에서 아래 두 값을 복사해 붙여넣으세요.\n"
            "통합의 '리디렉션 URI'에는 아래 주소가 그대로 들어가 있어야 해요.")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tk.Label(f, text="리디렉션 URI", font=font).grid(row=1, column=0, sticky="e", padx=(0, 8))
        uri = tk.Entry(f, width=42, font=font)
        uri.insert(0, NOTION_REDIRECT)
        uri.config(state="readonly")
        uri.grid(row=1, column=1, sticky="w", pady=3)
        tk.Label(f, text="클라이언트 ID", font=font).grid(row=2, column=0, sticky="e", padx=(0, 8))
        tk.Label(f, text="클라이언트 시크릿", font=font).grid(row=3, column=0, sticky="e", padx=(0, 8))
        cid = tk.Entry(f, width=42, font=font)
        csec = tk.Entry(f, width=42, font=font, show="•")
        cid.grid(row=2, column=1, sticky="w", pady=3)
        csec.grid(row=3, column=1, sticky="w", pady=3)
        cur = self.notion.client()
        if cur.get("client_id"):
            cid.insert(0, cur["client_id"])
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666", justify="left", text=(
            "'연결'을 누르면 브라우저에 Notion 허용 화면이 떠요. 페이지 선택에서\n"
            f"'{NOTION_PAGE_NAME}'을 체크하고 허용을 눌러 주세요.\n"
            "입력한 값과 받은 열쇠는 이 PC의 내 Windows 계정에서만 풀 수 있게 암호화해서 저장해요.")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 8))
        warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025")
        warn.grid(row=6, column=0, columnspan=2, sticky="w")

        def go():
            a, b = cid.get().strip(), csec.get().strip()
            if not a or not b:
                warn.config(text="클라이언트 ID와 시크릿을 둘 다 넣어 주세요.")
                return
            self.notion.save_client(a, b)
            d.destroy()
            self.say(f"브라우저에서 Notion '허용'을 눌러 주세요.\n(페이지 선택: {NOTION_PAGE_NAME})", 10)
            self.gcal_run("notion_auth", self.notion.authorize)

        btns = tk.Frame(f)
        btns.grid(row=5, column=0, columnspan=2, sticky="e")
        tk.Button(btns, text="연결", width=8, command=go).pack(side="left", padx=4)
        tk.Button(btns, text="취소", width=8, command=d.destroy).pack(side="left")
        apply_theme(d)
        (csec if cur.get("client_id") else cid).focus_set()

    def notion_disconnect(self):
        self.notion.disconnect()
        self.say("Notion 연결을 끊었어요.", 3)

    # ---------- 내 할 일 창 (Notion TODO, 표처럼 칸마다 바로 고침) ----------
    @staticmethod
    def todo_md(m, d):
        """'10/30' 처럼 연도 없이 쓴 날짜: 올해로, 두 달 넘게 지난 날짜면 내년으로 (없는 날짜면 ValueError)"""
        today = date.today()
        x = date(today.year, m, d)
        return x if x >= today - timedelta(days=60) else date(today.year + 1, m, d)

    def todo_due_text(self, iso):
        """기한 칸에 보이는 글: 짧게 써도 같은 날이면 '10/30', 아니면 '2027-01-05'"""
        if not iso:
            return ""
        d = date.fromisoformat(iso)
        try:
            short = self.todo_md(d.month, d.day) == d
        except ValueError:
            short = False
        return f"{d.month}/{d.day}" if short else d.isoformat()

    def todo_parse_due(self, s):
        """기한 칸 글 → (날짜 또는 None, 오류). '10/30'·'2026-10-30' 모두 가능"""
        s = s.strip()
        if not s:
            return None, None
        if not re.fullmatch(r"\d{1,4}[-/.]\d{1,2}([-/.]\d{1,2})?", s):
            return None, f"기한 '{s}' 은 10/30 이나 2026-10-30 처럼 적어 주세요."
        parts = [int(p) for p in re.split(r"[-/.]", s)]
        try:
            if len(parts) == 3:
                return date(parts[0] + (2000 if parts[0] < 100 else 0), parts[1], parts[2]), None
            return self.todo_md(parts[0], parts[1]), None
        except ValueError:
            return None, f"기한 '{s}' 는 없는 날짜예요."

    TODO_COLS = (("", 3), ("할 일", 36), ("기한", 12), ("분류", 9), ("", 6))

    def todo_window(self):
        if self.todo_alive():
            self.todo_win.lift()
            self.todo_win.focus_force()
            return
        d = self.dialog = self.todo_win = tk.Toplevel(self.root)
        d.title("내 할 일 - Notion TODO")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        f = tk.Frame(d, pady=12)
        f.pack(fill="both", expand=True)
        f.columnconfigure(0, weight=1)
        px = 14  # 표는 창 좌우 끝까지 꽉 차게, 나머지 글·버튼만 안쪽 여백
        tk.Label(f, text="내 할 일 (담당자가 나, 완료 아님)", font=("Malgun Gothic", 10, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=px)
        outer = tk.Frame(f, bg=UI_LINE, pady=1)
        outer.grid(row=1, column=0, columnspan=3, sticky="we", pady=(4, 4))
        # 1행(머리글)은 스크롤 밖에 고정, 2행부터 아래 칸에서 스크롤
        self.todo_head = tk.Frame(outer, bg=UI_LINE)
        self.todo_head.pack(fill="x")
        for c, (name, w) in enumerate(self.TODO_COLS):
            lab = tk.Label(self.todo_head, text=name, font=("Malgun Gothic", 9, "bold"), fg=UI_SUB, bg=UI_TRACK, pady=3)
            lab.grid(row=0, column=c, padx=(0, 1), pady=(0, 1), sticky="nsew")
        self.todo_head.columnconfigure(1, weight=1)
        self.todo_head_pad = tk.Frame(self.todo_head, bg=UI_TRACK)  # 아래 스크롤바 자리
        self.todo_head_pad.grid(row=0, column=len(self.TODO_COLS), pady=(0, 1), sticky="nsew")
        body = tk.Frame(outer, bg=UI_LINE)
        body.pack(fill="both", expand=True)
        self.todo_cv = cv = tk.Canvas(body, width=640, height=300, bg=UI_FIELD, highlightthickness=0)
        sb = tk.Scrollbar(body, command=cv.yview)
        cv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        self.todo_grid = tk.Frame(cv, bg=UI_LINE)  # 칸 사이 1px 틈에 이 배경이 비쳐 표의 선이 됨
        self.todo_grid.columnconfigure(1, weight=1)
        win = cv.create_window((0, 0), window=self.todo_grid, anchor="nw")
        self.todo_grid.bind("<Configure>", lambda e: (cv.configure(scrollregion=cv.bbox("all")), self.todo_sync_head()))
        cv.bind("<Configure>", lambda e: (cv.itemconfig(win, width=e.width), self.todo_sync_head()))
        d.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        d.bind("<Control-s>", lambda e: (self.todo_save(), "break")[-1])
        self.todo_status = tk.Label(f, font=("Malgun Gothic", 9), fg="#666")
        self.todo_status.grid(row=2, column=0, sticky="w", padx=(px, 0))
        btns = tk.Frame(f)
        btns.grid(row=2, column=1, columnspan=2, sticky="e", padx=(0, px))
        self.todo_save_btn = tk.Button(btns, text="저장 (Ctrl+S)", width=12, command=self.todo_save)
        self.todo_save_btn.pack(side="left", padx=2)
        tk.Button(btns, text="새로고침", command=self.todo_reload).pack(side="left", padx=2)
        self.todo_warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025", justify="left")
        self.todo_warn.grid(row=3, column=0, columnspan=3, sticky="w", padx=px)
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666", justify="left",
                 text="칸을 눌러 바로 고쳐요 · 맨 아래 빈 줄에 쓰면 새 할 일 · ☐ 는 완료 · ✕ 는 삭제(휴지통) · 저장해야 반영돼요").grid(
            row=4, column=0, columnspan=3, sticky="w", padx=px, pady=(2, 0))
        self.todo_items, self.todo_rows, self.todo_loaded, self.todo_busy = [], [], False, False
        apply_theme(d)
        d.focus_force()
        self.refresh_todos()

    def todo_alive(self):
        return self.todo_win is not None and self.todo_win.winfo_exists()

    def todo_dirty(self):
        if not self.todo_alive() or not self.todo_loaded:
            return False
        plan, err = self.todo_plan()
        return err is not None or any(plan.values())

    def refresh_todos(self):
        if self.todo_alive():
            self.todo_status.config(text="불러오는 중...")
            self.gcal_run("todos", self.notion.my_todos)

    def todo_reload(self):
        if self.todo_dirty():
            from tkinter import messagebox
            if not messagebox.askyesno("새로고침", "저장하지 않은 내용이 사라져요. 그래도 새로 불러올까요?", parent=self.todo_win):
                return
        self.refresh_todos()

    def todo_cell(self, r, c, widget_maker, bg=None):
        """표의 한 칸: 칸 사이 틈이 선처럼 보이게 1px 띄워서 놓음"""
        cell = tk.Frame(self.todo_grid, bg=bg or UI_FIELD)
        cell.grid(row=r, column=c, padx=(0, 1), pady=(0, 1), sticky="nsew")
        widget_maker(cell)
        return cell

    def show_todos(self, todos, err=None):
        if not self.todo_alive():
            return
        if err:
            self.todo_status.config(text=f"불러오지 못했어요: {str(err)[:60]}")
            return
        self.todo_items = todos
        self.todo_loaded = True
        self.todo_rows = []
        for w in self.todo_grid.winfo_children():
            w.destroy()
        for t in todos:
            self.todo_add_row(t)
        self.todo_add_row(None)
        self.todo_lock(False)
        self.todo_cv.yview_moveto(0)
        self.todo_win.after(30, self.todo_sync_head)
        self.todo_warn.config(text="")
        self.todo_changed()
        self.todo_status.config(text=f"{len(todos)}개 · {datetime.now():%H:%M} 기준")

    def todo_sync_head(self):
        """고정한 머리글 칸 너비를 아래 표의 칸 너비에 맞춤 (스크롤바 자리도 비워 둠)"""
        if not self.todo_alive() or not self.todo_rows:
            return
        try:
            for c in range(len(self.TODO_COLS)):
                self.todo_head.columnconfigure(c, minsize=self.todo_grid.grid_bbox(c, 0)[2], weight=1 if c == 1 else 0)
            sbw = self.todo_cv.master.winfo_width() - self.todo_cv.winfo_width()
            self.todo_head.columnconfigure(len(self.TODO_COLS), minsize=max(0, sbw))
        except tk.TclError:
            pass

    def todo_add_row(self, item):
        """표에 한 줄 추가 (item 이 None 이면 새 할 일을 쓰는 빈 줄)"""
        font = ("Malgun Gothic", 10)
        r = len(self.todo_rows)
        rec = {"item": item, "title": tk.StringVar(value=item["title"] if item else ""),
               "due": tk.StringVar(value=self.todo_due_text(item["due"]) if item else ""),
               "cat": tk.StringVar(value=(item["category"] or "(없음)") if item else "(없음)"),
               "done": tk.BooleanVar(value=False), "del": tk.BooleanVar(value=False), "inputs": []}
        self.todo_rows.append(rec)
        late = bool(item and item["due"] and item["due"] < date.today().isoformat())
        cats = list(dict.fromkeys(list(NOTION_TODO_CATEGORIES) + [t["category"] for t in self.todo_items if t["category"]]))

        def chk(p):
            if item:
                b = tk.Checkbutton(p, variable=rec["done"], bg=UI_FIELD, activebackground=UI_FIELD, bd=0,
                                   command=lambda: self.todo_style_row(rec))
                b.pack()
                rec["inputs"].append(b)
        self.todo_cell(r, 0, chk)

        def title(p):
            e = tk.Entry(p, textvariable=rec["title"], width=self.TODO_COLS[1][1], font=font, relief="flat",
                         bg=UI_FIELD, fg=UI_TEXT, insertbackground=UI_TEXT, highlightthickness=0)
            e.pack(fill="both", ipady=3, padx=2)
            e.bind("<Return>", lambda ev, rc=rec: self.todo_next_row(rc))
            rec["title_entry"] = e
            rec["inputs"].append(e)
        self.todo_cell(r, 1, title)

        def due(p):
            e = tk.Entry(p, textvariable=rec["due"], width=self.TODO_COLS[2][1] - 3, font=font, relief="flat",
                         bg=UI_FIELD, fg="#d93025" if late else UI_TEXT, insertbackground=UI_TEXT,
                         highlightthickness=0, cursor="hand2")
            e.pack(side="left", fill="both", ipady=3, padx=2)
            e.bind("<Button-1>", lambda ev: (self.todo_win.after(1, lambda: DatePicker(self.todo_win, e)), "break")[1])
            x = tk.Button(p, text="×", bd=0, bg=UI_FIELD, fg=UI_SUB, cursor="hand2", font=("Malgun Gothic", 9),
                          command=lambda: rec["due"].set(""))
            x.pack(side="left")
            rec["due_entry"] = e
            rec["inputs"] += [e, x]
        self.todo_cell(r, 2, due)

        def cat(p):
            m = tk.OptionMenu(p, rec["cat"], "(없음)", *cats)
            m.config(width=self.TODO_COLS[3][1] - 2, font=("Malgun Gothic", 9), bd=0, highlightthickness=0, bg=UI_FIELD)
            m.pack(fill="both")
            rec["inputs"].append(m)
        self.todo_cell(r, 3, cat)

        def acts(p):
            if item:
                o = tk.Button(p, text="↗", bd=0, bg=UI_FIELD, fg=UI_SKY, cursor="hand2",
                              command=lambda: item.get("url") and webbrowser.open(item["url"]))
                o.pack(side="left", padx=(4, 0))
                x = tk.Button(p, text="✕", bd=0, bg=UI_FIELD, fg="#d93025", cursor="hand2",
                              command=lambda: (rec["del"].set(not rec["del"].get()), self.todo_style_row(rec)))
                x.pack(side="left", padx=(6, 0))
                rec["inputs"] += [o, x]
        self.todo_cell(r, 4, acts)
        for v in (rec["title"], rec["due"], rec["cat"]):
            v.trace_add("write", lambda *a, rc=rec: self.todo_on_edit(rc))

    def todo_on_edit(self, rec):
        # 맨 아래 빈 줄에 쓰기 시작하면 다음 빈 줄을 하나 더 만들어 줌
        if rec is self.todo_rows[-1] and rec["item"] is None and rec["title"].get().strip():
            self.todo_add_row(None)
        self.todo_changed()

    def todo_next_row(self, rec):
        i = self.todo_rows.index(rec)
        if i + 1 < len(self.todo_rows):
            self.todo_rows[i + 1]["title_entry"].focus_set()

    def todo_style_row(self, rec):
        """완료·삭제로 표시한 줄은 취소선 + 흐리게"""
        font = ("Malgun Gothic", 10, "overstrike") if (rec["done"].get() or rec["del"].get()) else ("Malgun Gothic", 10)
        rec["title_entry"].config(font=font, fg=UI_SUB if (rec["done"].get() or rec["del"].get()) else UI_TEXT)
        self.todo_changed()

    def todo_lock(self, flag):
        self.todo_busy = flag
        st = "disabled" if flag else "normal"
        for rec in self.todo_rows:
            for w in rec["inputs"]:
                try:
                    w.config(state=st)
                except tk.TclError:
                    pass
        self.todo_save_btn.config(state=st)

    def todo_changed(self):
        if not self.todo_alive() or not self.todo_loaded or self.todo_busy:
            return
        plan, err = self.todo_plan()
        n = sum(len(v) for v in plan.values()) if plan else 0
        if err:
            self.todo_status.config(text="고치는 중...")
        elif n:
            self.todo_status.config(text=f"저장하지 않은 변경 {n}개")
        else:
            self.todo_status.config(text=f"{len(self.todo_items)}개 · {datetime.now():%H:%M} 기준")

    def todo_plan(self):
        """표 내용 → 바뀐 것 계획 {'update','add','delete','done'}. 오류가 있으면 (None, 메시지)"""
        plan = {"update": [], "add": [], "delete": [], "done": []}
        for rec in self.todo_rows:
            it = rec["item"]
            title = " ".join(rec["title"].get().split())
            due, err = self.todo_parse_due(rec["due"].get())
            cat = None if rec["cat"].get() == "(없음)" else rec["cat"].get()
            if it is None:
                if not title:
                    if rec["due"].get().strip() or cat:
                        return None, "새 줄에 기한·분류만 있고 할 일 제목이 없어요."
                    continue
                if err:
                    return None, f"'{title}': {err}"
                plan["add"].append((title, due, cat))
                continue
            if rec["del"].get():
                plan["delete"].append(it["id"])
                continue
            if rec["done"].get():
                plan["done"].append(it["id"])
                continue
            if err:
                return None, f"'{title or it['title']}': {err}"
            if not title:
                return None, "제목이 빈 할 일이 있어요. (지우려면 ✕ 를 눌러 주세요)"
            od = date.fromisoformat(it["due"]) if it["due"] else None
            if (title, due, cat) != (" ".join(it["title"].split()), od, it["category"] or None):
                plan["update"].append((it["id"], title, due, cat))
        return plan, None

    def todo_save(self):
        if not self.todo_alive() or not self.todo_loaded or self.todo_busy:
            return
        plan, err = self.todo_plan()
        if err:
            self.todo_warn.config(text=err)
            return
        self.todo_warn.config(text="")
        if not any(plan.values()):
            self.todo_status.config(text="바뀐 게 없어요")
            return
        if plan["delete"]:
            from tkinter import messagebox
            names = [o["title"] for o in self.todo_items if o["id"] in plan["delete"]]
            msg = f"지운 할 일 {len(names)}개를 Notion 에서도 지울까요? (휴지통으로 가요)\n\n" + "\n".join(
                f"· {s[:40]}" for s in names[:8]) + ("\n..." if len(names) > 8 else "")
            if not messagebox.askyesno("할 일 삭제", msg, parent=self.todo_win):
                return
        self.todo_status.config(text="Notion 에 저장하는 중...")
        self.todo_lock(True)
        self.gcal_run("todo_save", self.notion.save_todos, plan)

    def show_schedule(self, events):
        if self.sched_win is None or not self.sched_win.winfo_exists():
            return
        self.sched_events = events
        self.sched_list.delete(0, "end")
        for ev in events:
            self.sched_list.insert("end", self.event_label(ev))
        if not events:
            self.sched_list.insert("end", "  앞으로 2주 동안 일정이 없어요.")
        self.sched_status.config(text=f"{len(events)}개 · {datetime.now():%H:%M} 기준")

    def update_pet(self, now):
        dt = min(now - self.last_tick, 1.0)
        self.last_tick = now
        if self.is_day_off(date.today()):
            dt = 0.0  # 쉬는 날에는 배고픔·기분이 줄지 않음
        self.full = max(0.0, self.full - FULL_DECAY * dt / UNIT)
        self.mood = max(0.0, self.mood - MOOD_DECAY * dt / UNIT)
        if now - self.last_save > 30:
            self.last_save = now
            self.save_pet()
        if (now - self.last_whine > WHINE_MIN * UNIT and self.pomo_phase != "focus"
                and not self.bubble_until and dt > 0):
            if self.full < 30:
                self.last_whine = now
                self.say("배고파요...\n(우클릭 → 밥 주기)", 5)
            elif self.mood < 30:
                self.last_whine = now
                self.say("심심해요...\n(우클릭 → 놀아주기)", 5)
        for it in list(self.items):
            it.update()
