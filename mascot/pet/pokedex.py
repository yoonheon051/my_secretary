"""포켓몬 도감·포켓몬 바꾸기"""

import os
import time
import tkinter as tk
import webbrowser

from ..constants import GRUMPY_AT, HUNGRY_AT
from ..species import SPECIES_DIR, species_defs
from ..ui import UI_ACCENT, UI_FIELD, UI_HOVER, UI_LINE, UI_TRACK, apply_theme


class PokedexMixin:
    # ---------- 포켓몬 도감 · 포켓몬 바꾸기 ----------
    DEX_TYPE_COLORS = {"노말": "#a8a878", "불꽃": "#f08030", "물": "#6890f0", "전기": "#f8d030", "풀": "#78c850",
                       "얼음": "#98d8d8", "격투": "#c03028", "독": "#a040a0", "땅": "#e0c068", "비행": "#a890f0",
                       "에스퍼": "#f85888", "벌레": "#a8b820", "바위": "#b8a038", "고스트": "#705898", "드래곤": "#7038f8",
                       "악": "#705848", "강철": "#b8b8d0", "페어리": "#ee99ac"}

    def species_record(self, sid):
        """그 포켓몬을 키운 기록 (레벨, 볼 이름, 친밀도). 함께한 적이 없으면 None"""
        if sid == self.species_id:
            aff = self.affection
        else:
            rec = self.pets.get(sid)
            if not rec:
                return None
            aff = rec.get("affection", 0.0)
        lv = 1 + int(aff // 10)
        balls = self.species_defs[sid]["balls"]
        ball = max((b for b in balls if lv >= b["level"]), key=lambda b: b["level"], default=balls[0])
        return lv, ball["name"], aff

    def switch_species(self, sid):
        """다른 포켓몬과 함께하기: 지금 포켓몬의 기록을 저장하고, 새 포켓몬이 볼에서 나옴. 바꿨으면 True"""
        defs = species_defs()
        sp = defs.get(sid)
        if sp is None or not sp["ok"] or sid == self.species_id:
            return False
        if self.in_ball or self.pomo_phase == "focus" or self.shutdown_at is not None \
                or self.state in ("toball", "capture", "release", "focus"):
            self.say("재우는 중이거나 종료 예고 중에는\n포켓몬을 바꿀 수 없어요.", 4)
            return False
        self.species_defs = defs
        self.save_pet()  # 지금 포켓몬의 기록을 pets 에 저장
        self.species_id, self.species = sid, sp
        cur = self.pets.get(sid) or {"full": 80.0, "mood": 80.0, "affection": 0.0}
        self.full, self.mood, self.affection = cur["full"], cur["mood"], cur.get("affection", 0.0)
        self.load_character()
        self.set_travel_room(False)
        self.canvas.config(width=self.W, height=self.H)
        self.last_sig = self.last_pos = None
        self.ball_sig = None
        self.set_ball_front(False)
        self.surface = self.left_surface = None
        self.visit = None
        self.pick_monitor()
        self.y = self.ground()  # 창 높이가 포켓몬마다 달라서, 예전 높이 그대로면 발밑이 없다고 보고 떨어져 버림
        self.vx = self.vy = 0.0
        self.in_ball = True  # 볼에서 새 포켓몬이 나오는 모습으로
        self.root.withdraw()
        self.start_release(time.time())
        self.save_pet()
        self.say("나왔어요!", 4)
        return True

    def pokedex_entries(self):
        """도감에 올릴 포켓몬들 (번호 순)"""
        self.species_defs = species_defs()
        out = []
        for sid, sp in self.species_defs.items():
            out.append(dict(sp, current=sid == self.species_id, ready=sp["ok"]))
        out.sort(key=lambda e: (e["no"] is None, e["no"] or 0, e["name"]))
        return out

    def show_pokedex(self):
        if self.dex_win is not None and self.dex_win.winfo_exists():
            self.dex_win.lift()
            self.dex_win.focus_force()
            return
        entries = self.pokedex_entries()
        d = self.dialog = self.dex_win = tk.Toplevel(self.root)
        d.title("포켓몬 도감")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        font, small, bold = ("Malgun Gothic", 10), ("Malgun Gothic", 9), ("Malgun Gothic", 10, "bold")
        f = tk.Frame(d, padx=14, pady=12)
        f.pack()
        tk.Label(f, text="포켓몬 도감", font=("Malgun Gothic", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        lv, ball, _ = self.species_record(self.species_id)
        tk.Label(f, font=small, fg="#666", text=f"함께하는 포켓몬: {self.species['name']} · Lv.{lv} · {ball}").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        side = tk.Frame(f, bg=UI_LINE, padx=1, pady=1)
        side.grid(row=2, column=0, sticky="ns")
        listf = tk.Frame(side, bg=UI_FIELD)
        listf.pack(fill="both", expand=True)
        detail = tk.Frame(f, padx=14, width=420, height=480)
        detail.grid(row=2, column=1, sticky="nw")
        detail.grid_propagate(False)
        self.dex_imgs = []  # 그림이 사라지지 않게 붙들어 둠
        rows = {}

        def thumb(path, target):
            """그림을 높이 target 근처로 줄여서 (정수 배)"""
            try:
                im = tk.PhotoImage(file=path)
                shrink = max(1, round(im.height() / target))
                if shrink > 1:
                    t = tk.PhotoImage()
                    t.tk.call(t, "copy", im, "-subsample", shrink, shrink)
                    im = t
                self.dex_imgs.append(im)
                return im
            except tk.TclError:
                return None

        def together(e):
            if self.switch_species(e["id"]):
                self.dex_win.destroy()
                self.dex_win = None
                self.root.after(100, self.show_pokedex)

        def select(e):
            for k, (row, lab) in rows.items():
                row.config(bg=UI_HOVER if k == e["id"] else UI_FIELD)
                for w in row.winfo_children():
                    w.config(bg=UI_HOVER if k == e["id"] else UI_FIELD)
            for w in detail.winfo_children():
                w.destroy()
            im = thumb(e["image"], 110) if e.get("image") else None
            pic = tk.Label(detail, image=im, text="" if im else "(그림 없음)", width=10 if not im else 0,
                           height=5 if not im else 0, font=small, fg="#888")
            pic.grid(row=0, column=0, rowspan=3, padx=(0, 12))
            no = f"No.{e['no']:03d}" if e.get("no") else "No.???"
            tk.Label(detail, text=no, font=small, fg="#777").grid(row=0, column=1, sticky="sw")
            tk.Label(detail, text=e["name"] + (f"  {e['en']}" if e.get("en") else ""),
                     font=("Malgun Gothic", 13, "bold")).grid(row=1, column=1, sticky="w")
            tk.Label(detail, text=e.get("kind", ""), font=small, fg="#666").grid(row=2, column=1, sticky="nw")
            chips = tk.Frame(detail)
            chips.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
            for t in e.get("types", []):
                tk.Label(chips, text=t, font=("Malgun Gothic", 9, "bold"), bg=self.DEX_TYPE_COLORS.get(t, "#999"),
                         fg="white", padx=8, pady=1).pack(side="left", padx=(0, 4))
            tk.Label(detail, text=e.get("desc") or "(설명이 아직 없어요)", font=font, wraplength=330,
                     justify="left").grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
            rec = self.species_record(e["id"])
            tk.Label(detail, font=small, fg="#666",
                     text=(f"키운 기록: Lv.{rec[0]} · {rec[1]}" if rec
                           else "아직 함께한 적 없어요")).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
            if rec:  # 배부름·기분·친밀도 막대 (함께하지 않는 포켓몬은 마지막으로 헤어질 때 값)
                if e["current"]:
                    vals = {"full": self.full, "mood": self.mood, "affection": self.affection}
                else:
                    pet = self.pets.get(e["id"], {})
                    vals = {"full": pet.get("full", 80.0), "mood": pet.get("mood", 80.0), "affection": pet.get("affection", 0.0)}
                bars = tk.Frame(detail)
                bars.grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
                for r, (key, label, color) in enumerate(self.CARD_BARS):
                    v = vals[key]
                    if key == "affection":
                        frac, text, fill = (v % 10) / 10, f"{int(v % 10)}/10", color
                    else:
                        low = v <= (HUNGRY_AT if key == "full" else GRUMPY_AT)
                        frac, text, fill = v / 100, str(int(v)), self.CARD_LOW if low else color
                    tk.Label(bars, text=label, font=small, fg="#666", width=6, anchor="w").grid(row=r, column=0, sticky="w")
                    bar = tk.Canvas(bars, width=150, height=10, bg=UI_TRACK, highlightthickness=0)
                    bar.grid(row=r, column=1, padx=(4, 6), pady=3)
                    bar.create_rectangle(0, 0, round(150 * max(0.0, min(1.0, frac))), 10, fill=fill, outline="")
                    tk.Label(bars, text=text, font=small, fg="#666", width=5, anchor="w").grid(row=r, column=2, sticky="w")
            btns = tk.Frame(detail)
            btns.grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))
            if e["current"]:
                tk.Label(btns, text="함께하는 중 ✔", font=bold, fg=UI_ACCENT).pack(side="left", padx=(0, 10))
            elif e["ready"]:
                tk.Button(btns, text="함께 키우기", command=lambda e=e: together(e)).pack(side="left", padx=(0, 6))
            else:
                tk.Label(btns, text="평소 모습 그림이 필요해요", font=small, fg="#d93025").pack(side="left", padx=(0, 10))
            if e.get("web"):
                tk.Button(btns, text="웹 도감에서 보기", command=lambda u=e["web"]: webbrowser.open(u)).pack(side="left")
            apply_theme(detail)  # 새로 만든 글자들에도 창 색을 입힘

        for e in entries:
            row = tk.Frame(listf, bg=UI_FIELD, cursor="hand2", padx=6, pady=4)
            row.pack(fill="x")
            im = thumb(e["image"], 55) if e.get("image") else None
            pic = tk.Label(row, image=im, text="" if im else "?", width=7 if not im else 0, bg=UI_FIELD, fg="#aaa")
            pic.pack(side="left")
            txt = f"#{e['no']:03d}  {e['name']}" if e.get("no") else e["name"]
            lab = tk.Label(row, text=txt + ("  ✔" if e["current"] else ""), font=font, bg=UI_FIELD, width=14, anchor="w")
            lab.pack(side="left", padx=(6, 0))
            rows[e["id"]] = (row, lab)
            for w in (row, pic, lab):
                w.bind("<Button-1>", lambda ev, e=e: select(e))
                w.bind("<Double-Button-1>", lambda ev, e=e: together(e) if e["ready"] and not e["current"] else None)
        add = tk.Frame(f)
        add.grid(row=3, column=0, columnspan=2, sticky="we", pady=(12, 0))
        tk.Frame(add, height=1, bg=UI_LINE).pack(fill="x", pady=(0, 8))
        tk.Label(add, font=small, fg="#666", justify="left", anchor="w",
                 text="새 포켓몬은 pokemon 폴더의 _양식 폴더를 복사해 이름을 바꾸고, pokemon.json 을 고친 뒤\n"
                      "평소 모습 character.png 를 넣으면 도감에 나타나요. (자세한 설명은 _양식 안의 README.txt)").pack(fill="x")

        def open_dir():
            os.makedirs(SPECIES_DIR, exist_ok=True)
            os.startfile(SPECIES_DIR)
        tk.Button(add, text="pokemon 폴더 열기", command=open_dir).pack(anchor="w", pady=(6, 0))
        apply_theme(d)
        select(next((e for e in entries if e["current"]), entries[0]))  # 처음엔 함께하는 포켓몬
        d.focus_force()
