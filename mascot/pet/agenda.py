"""휴일·Google 캘린더 연결·오늘 일정·내 일정 창"""

import json
import queue
import threading
import time
import tkinter as tk
from datetime import date, datetime, timedelta

from ..constants import (
    GCAL_SYNC_SEC,
    HOLIDAY_CACHE,
    HOLIDAY_REFRESH_SEC,
    NOTION_CAL_DB,
    REPORT_CHECK_HOUR,
    REPORT_CLOSE_AT,
)
from ..holidays import HolidayFetcher
from ..ui import DatePicker, apply_theme


class AgendaMixin:
    # ---------- 휴일 ----------
    def is_day_off(self, d):
        return d.weekday() >= 5 or d.isoformat() in self.off_days

    def workday_seconds(self, t0, t1):
        """t0~t1 사이 시간 중 쉬는 날이 아닌 날에 속한 초"""
        total, t = 0.0, t0
        while t < t1:
            d = datetime.fromtimestamp(t).date()
            seg_end = min(t1, datetime.combine(d + timedelta(days=1), datetime.min.time()).timestamp())
            if not self.is_day_off(d):
                total += seg_end - t
            t = seg_end
        return total

    def load_holiday_cache(self):
        try:
            with open(HOLIDAY_CACHE, encoding="utf-8") as fp:
                c = json.load(fp)
            self.public_days, self.personal_days = set(c.get("public", [])), set(c.get("personal", []))
        except (OSError, ValueError):
            self.public_days, self.personal_days = set(), set()
        self.rebuild_off_days()

    def rebuild_off_days(self):
        self.off_days = self.public_days | self.personal_days

    def update_holidays(self, now):
        if now - self.last_holiday_fetch > HOLIDAY_REFRESH_SEC:
            self.last_holiday_fetch = now
            HolidayFetcher(self.holiday_q).start()
        try:
            public = self.holiday_q.get_nowait()
        except queue.Empty:
            public = None
        if public is not None:
            self.public_days = public
            self.rebuild_off_days()
            self.save_holiday_cache()
        off = self.is_day_off(date.today())
        if off and self.was_day_off is False:
            self.say("오늘은 쉬는 날!\n배고픔도 기분도 그대로 기다릴게요.", 5)
        self.was_day_off = off

    # ---------- Google Calendar API ----------
    def gcal_run(self, kind, fn, *args):
        """캘린더 작업을 스레드에서 실행하고 결과를 gcal_q 로 (화면이 멈추지 않게)"""
        def work():
            try:
                self.gcal_q.put((kind, fn(*args), None))
            except Exception as e:
                self.gcal_q.put((kind, None, e))
        threading.Thread(target=work, daemon=True).start()

    def gcal_connect(self):
        if not self.gcal.has_client():
            self.say("client_secret.json 이 필요해요.\nGoogle Cloud Console 에서 받은 파일을\n프로그램 폴더에 넣어 주세요.", 8)
            return
        self.say("브라우저에서 Google 계정으로\n'허용'을 눌러 주세요.", 8)
        self.gcal_run("auth", self.gcal.authorize)

    def gcal_disconnect(self):
        self.gcal_run("disconnect", self.gcal.disconnect)

    def update_gcal(self, now):
        if self.gcal.connected and now - self.last_gcal_sync > GCAL_SYNC_SEC:
            self.last_gcal_sync = now
            self.gcal_run("sync", self.gcal.find_days, "연차")
        if self.notion.connected and self.crossed(30):
            if now - self.last_notion_sync > GCAL_SYNC_SEC:  # Notion '휴가' 일정
                self.last_notion_sync = now
                self.gcal_run("notion_vac", self.notion.my_vacation_days)
            t = datetime.now()
            today = t.date().isoformat()
            if (t.hour == REPORT_CHECK_HOUR and self.report_checked != today
                    and not self.is_day_off(t.date())):  # 평일 18시: 퇴근 전 마무리 요약 + 일일보고 확인
                self.report_checked = today
                self.gcal_run("report", self.notion.day_wrap)
            if ((t.hour, t.minute) >= REPORT_CLOSE_AT and self.report_closed != today
                    and not self.is_day_off(t.date())):  # 평일 18:30: 마감 버튼을 대신 누름
                self.report_closed = today
                texts = self.report_parse() if self.report_dirty() else None  # 창에 쓰다 만 글이 있으면 같이 저장
                self.gcal_run("report_auto", self.notion.auto_close_report, texts)
        try:
            kind, result, err = self.gcal_q.get_nowait()
        except queue.Empty:
            return
        if kind == "auth":
            if err:
                self.say(f"캘린더 연결에 실패했어요.\n{str(err)[:80]}", 8)
            else:
                self.say("Google 캘린더 연결 완료!\n연차를 읽어 오고, 일정도 바로 넣을게요.", 6)
                self.last_gcal_sync = 0  # 바로 연차 읽기
                self.sync_announce = True
        elif kind == "sync":
            if err is None:
                self.apply_vacations(result, "google")
                if self.sync_announce:
                    self.say(f"캘린더에서 연차 {len([d for d in result if d >= date.today().isoformat()])}일을\n"
                             f"찾았어요. 그날은 저도 쉬어요!", 5)
            self.sync_announce = False
        elif kind == "insert":
            if err:
                self.say(f"일정을 넣지 못했어요.\n{str(err)[:80]}", 8)
            else:
                self.say(f"캘린더에 일정을 넣었어요!\n「{result.get('summary', '')[:30]}」", 5)
                if "연차" in result.get("summary", ""):
                    self.last_gcal_sync = 0  # 연차면 바로 휴일에 반영
            self.refresh_schedule()
        elif kind == "list":
            if err:
                if self.sched_win is not None and self.sched_win.winfo_exists():
                    self.sched_status.config(text=f"불러오지 못했어요: {str(err)[:60]}")
            else:
                self.show_schedule(result)
        elif kind == "delete":
            if err:
                self.say(f"일정을 지우지 못했어요.\n{str(err)[:80]}", 8)
            else:
                self.say("일정을 지웠어요.", 3)
                self.last_gcal_sync = 0  # 지운 게 연차였을 수도 있으니 다시 읽기
            self.refresh_schedule()
        elif kind == "agenda":
            if err:
                self.say(f"오늘 일정을 불러오지 못했어요.\n{str(err)[:80]}", 6)
            else:
                self.today_data, self.today_at = result, time.time()
                self.say(self.agenda_text(*result), 14)
        elif kind == "status_today":
            if err is None:
                self.today_data, self.today_at = result, time.time()
                self.refresh_status()
        elif kind == "notion_vac":
            if err is None:
                self.apply_vacations(result, "notion")
        elif kind == "report":  # 퇴근 전 마무리 요약 (NotionClient.day_wrap)
            if err is None:
                self.say(self.wrap_text(result), 20)
                if self.state in ("idle", "walk", "sleep", "home"):
                    self.set_state("happy", 1.0)
        elif kind == "morning":  # 출근 인사 + 오늘 할 일
            if err is None:
                self.say(self.morning_text(*result), 15)
                if self.state in ("idle", "walk", "sleep", "home"):
                    self.set_state("happy", 1.2)
        elif kind == "todos":
            self.show_todos(result, err)
        elif kind in ("todo_done", "todo_add"):
            if err:
                self.say(f"Notion 에 반영하지 못했어요.\n{str(err)[:80]}", 8)
            else:
                self.say("할 일을 완료했어요! 수고했어요." if kind == "todo_done" else "할 일을 Notion 에 넣었어요!", 4)
                if kind == "todo_done":
                    self.gain(mood=3)
                self.today_at = 0.0  # 상태 카드를 다음에 열 때 할 일 수를 다시 읽게
            self.refresh_todos()
        elif kind == "todo_save":  # 할 일 창(메모장)에서 저장
            if err:
                self.say(f"Notion 에 반영하지 못했어요.\n{str(err)[:80]}", 8)
                if self.todo_alive():
                    self.todo_status.config(text="실패했어요 (쓴 내용은 그대로예요)")
                    self.todo_lock(False)
                return  # 실패하면 다시 불러오지 않고 쓰던 내용을 남김
            self.today_at = 0.0
            if result.get("done"):
                self.gain(mood=3)
            if self.todo_alive():
                self.todo_status.config(text=f"저장했어요 ({result['summary']})")
            else:
                self.say(f"할 일을 저장했어요! ({result['summary']})", 3)
            self.refresh_todos()
        elif kind == "report_auto":  # 18:30 자동 마감 (NotionClient.auto_close_report)
            if err:
                self.say(f"18:30 자동 마감에 실패했어요.\n{str(err)[:80]}", 8)
            elif result == "closed":
                self.say("18:30이라 일일 업무를 마감했어요!", 5)
            if self.report_alive():
                self.refresh_report()
        elif kind == "report_view":
            self.show_report(result, err)
        elif kind == "report_edit":  # 일일 업무 창에서 쓰기·수정·삭제·마감
            if err:
                self.say(f"일일 업무에 반영하지 못했어요.\n{str(err)[:80]}", 8)
                if self.report_alive():
                    self.rep_status.config(text="실패했어요 (쓴 내용은 그대로예요)")
                    if self.rep_data and self.rep_data.get("exists"):
                        self.rep_text.config(state="normal")
                        self.rep_save_btn.config(state="normal")
                return  # 실패하면 다시 불러오지 않고 쓰던 글을 남김
            else:
                if self.report_alive():
                    self.rep_status.config(text="반영했어요")
                else:
                    self.say("일일 업무를 반영했어요!", 3)
            self.refresh_report()
        elif kind == "disconnect":
            self.say("Google 캘린더 연결을 끊었어요.", 3)
        elif kind == "notion_auth":
            if err:
                self.say(f"Notion 연결에 실패했어요.\n{str(err)[:90]}", 10)
            else:
                self.gcal_run("notion_check", self.notion.check)
        elif kind == "notion_check":
            if err:
                self.say(f"Notion 에 연결은 됐는데 읽지 못했어요.\n{str(err)[:90]}", 10)
            else:
                dbs = result["databases"]
                shown = ", ".join(dbs[:4]) + (f" 외 {len(dbs) - 4}개" if len(dbs) > 4 else "")
                self.say(f"Notion 연결 완료! ({result['workspace']})\n볼 수 있는 데이터베이스 {len(dbs)}개\n{shown}", 10)

    # ---------- 오늘 일정 한눈에 ----------
    AGENDA_MAX = 6  # 말풍선에 보여 줄 최대 일정 수

    @property
    def has_schedule_source(self):
        return self.gcal.connected or self.notion.connected

    def gather_events(self, days):
        """Google 캘린더 일정 + Notion 팀 일정을 한 목록으로 (시간 순). 스레드에서 부름"""
        events = []
        if self.gcal.connected:
            events += [dict(ev, source="google") for ev in self.gcal.list_events(days)]
        if self.notion.connected:
            today = date.today()
            events += self.notion.team_events(today, today + timedelta(days=days))
        events.sort(key=lambda ev: (ev["start"][:10], 0 if ev["all_day"] else 1, ev["start"]))
        return events

    def gather_today(self):
        """오늘 일정(Google + Notion 팀 일정)과 오늘 마감·기한 지난 내 Notion 할 일"""
        todos = self.notion.my_todos() if self.notion.connected else None
        return self.gather_events(1), todos

    def show_agenda(self):
        self.agenda_date = date.today().isoformat()
        self.say("오늘 일정을 확인해 볼게요...", 3)
        self.gcal_run("agenda", self.gather_today)

    def agenda_text(self, events, todos=None):
        """'오늘 일정 3개예요\n· 10:00~11:00 주간 회의 (끝남)\n· [팀] 하루 종일 장비 점검' + 오늘 할 일 말풍선 내용"""
        lines = self.agenda_event_lines(events) if events else ["오늘은 일정이 없어요."]
        if todos is not None:
            today = date.today().isoformat()
            due = [t for t in todos if t["due"] and t["due"] <= today]
            late = [t for t in due if t["due"] < today]
            if due:
                lines.append(f"할 일: 오늘 마감 {len(due) - len(late)}개 · 기한 지남 {len(late)}개")
                for t in due[:4]:
                    lines.append(f"· {t['title'][:22]}" + (" (기한 지남)" if t["due"] < today else " (오늘)"))
            elif todos:
                lines.append(f"할 일: 오늘 마감은 없어요 (남은 할 일 {len(todos)}개)")
        if not events and not (todos and any(t["due"] and t["due"] <= date.today().isoformat() for t in todos)):
            lines.append("여유로운 하루 보내요!")
        return "\n".join(lines)

    def wrap_text(self, w):
        """'오늘도 수고했어요! / 끝낸 할 일 2개: ... / 남은 할 일 3개 (기한 지남 1) / 일일 업무 ...'"""
        today = date.today().isoformat()
        lines = ["오늘도 수고했어요! 마무리 요약이에요."]
        done = w["done"]
        if done:
            names = ", ".join(t[:14] for t in done[:3]) + (f" 외 {len(done) - 3}개" if len(done) > 3 else "")
            lines.append(f"· 끝낸 할 일 {len(done)}개: {names}")
        else:
            lines.append("· 오늘 완료로 바꾼 할 일은 없어요")
        todos = w["todos"]
        late = sum(1 for t in todos if t["due"] and t["due"] < today)
        due = sum(1 for t in todos if t["due"] == today)
        extra = ", ".join(s for s in (f"오늘 마감 {due}" if due else "", f"기한 지남 {late}" if late else "") if s)
        lines.append(f"· 남은 할 일 {len(todos)}개" + (f" ({extra})" if extra else ""))
        r = w["report"]
        if r["done"]:
            lines.append("· 일일 업무 Done 완료!")
        else:
            self.report_url = r["url"] or f"https://www.notion.so/{NOTION_CAL_DB.replace('-', '')}"
            lines.append("· 일일 업무 " + ("아직 Done 이 아니에요" if r["exists"] else "아직 안 썼어요")
                         + " (18:30 마감)\n  저를 클릭하면 열어 드릴게요")
        return "\n".join(lines)

    def morning_text(self, events, todos):
        """'좋은 아침이에요! / 오늘 일정 2개 · 첫 일정 10:00 ... / 할 일: 오늘 마감 1개, 기한 지남 1개'"""
        today = date.today().isoformat()
        lines = ["좋은 아침이에요!"]
        if events:
            lines.append(f"· 오늘 일정 {len(events)}개 · {self.next_event_text(events)}")
        else:
            lines.append("· 오늘은 일정이 없어요")
        if todos is not None:
            due = [t for t in todos if t["due"] == today]
            late = [t for t in todos if t["due"] and t["due"] < today]
            if due or late:
                parts = [s for s in (f"오늘 마감 {len(due)}개" if due else "", f"기한 지남 {len(late)}개" if late else "") if s]
                lines.append("· 할 일: " + ", ".join(parts))
                for t in (late + due)[:3]:
                    lines.append(f"   - {t['title'][:22]}")
            else:
                lines.append(f"· 오늘 마감인 할 일은 없어요 (남은 할 일 {len(todos)}개)")
        return "\n".join(lines)

    def agenda_event_lines(self, events):
        now = datetime.now()
        today = now.date()
        lines = [f"오늘 일정 {len(events)}개예요"]
        for ev in events[:self.AGENDA_MAX]:
            if ev["all_day"]:
                when, state = "하루 종일 ", ""
            else:
                local = lambda t: datetime.fromisoformat(t).astimezone().replace(tzinfo=None)  # PC 시간대(서울)로
                s = local(ev["start"])
                e = local(ev["end"]) if ev["end"] else s
                s_txt = f"{s:%H:%M}" if s.date() == today else "어제부터"
                e_txt = f"{e:%H:%M}" if e.date() == today else f"{e.month}/{e.day} {e:%H:%M}"
                when = f"{s_txt}~{e_txt}"
                state = " (끝남)" if e <= now else (" (진행 중)" if s <= now else "")
            tag = "[팀] " if ev.get("source") == "notion" else ""
            lines.append(f"· {when} {tag}{ev['summary'][:20]}{state}")
        if len(events) > self.AGENDA_MAX:
            lines.append(f"  외 {len(events) - self.AGENDA_MAX}개")
        return lines

    def apply_vacations(self, days, source="google"):
        """내 휴가 날짜를 휴일에 반영. 출처별(google 연차 / notion 휴가 / mail)로 받아서 합침.
        지난 휴가는 꺼 둔 동안의 계산에 필요해서 120일까지 남겨 둠"""
        self.vac_sources[source] = set(days)
        today = date.today()
        keep_from = (today - timedelta(days=120)).isoformat()
        past = {d for d in self.personal_days if keep_from <= d < today.isoformat()}
        new = past | set().union(*self.vac_sources.values())
        if new != self.personal_days:
            self.personal_days = new
            self.rebuild_off_days()
            self.save_holiday_cache()

    def save_holiday_cache(self):
        try:
            with open(HOLIDAY_CACHE, "w", encoding="utf-8") as fp:
                json.dump({"public": sorted(self.public_days), "personal": sorted(self.personal_days),
                           "t": time.time()}, fp)
        except OSError:
            pass

    # ---------- 내 일정 창 (Google Calendar API) ----------
    WEEKDAYS_KO = "월화수목금토일"

    def event_label(self, ev):
        """목록에 보일 한 줄: '10/22(수) 14:00~15:00  팀 회의' / '10/23(목) 하루 종일  연차'"""
        d = date.fromisoformat(ev["start"][:10])
        head = f"{d.month}/{d.day}({self.WEEKDAYS_KO[d.weekday()]})"
        if ev["all_day"]:
            last = date.fromisoformat(ev["end"][:10]) - timedelta(days=1) if ev["end"] else d
            when = "하루 종일" if last <= d else f"~{last.month}/{last.day} 종일"
        else:
            e = date.fromisoformat(ev["end"][:10]) if ev["end"] else d
            tail = ev["end"][11:16] if e == d else f"{e.month}/{e.day} {ev['end'][11:16]}"
            when = f"{ev['start'][11:16]}~{tail}"
        tag = "[팀] " if ev.get("source") == "notion" else ""
        return f"{head} {when:<11} {tag}{ev['summary']}"

    def schedule_window(self):
        """오늘부터 2주 일정 목록 + 일정 추가 칸. 목록은 캘린더에서 읽어 오고, 추가·삭제는 캘린더에 바로 반영"""
        if self.sched_win is not None and self.sched_win.winfo_exists():
            self.sched_win.lift()
            return
        d = self.dialog = self.sched_win = tk.Toplevel(self.root)
        d.title("내 일정 - Google 캘린더 · Notion 팀 일정")
        d.attributes("-topmost", True)
        d.resizable(False, False)
        f = tk.Frame(d, padx=14, pady=12)
        f.pack()
        font = ("Malgun Gothic", 10)

        tk.Label(f, text="앞으로 2주 일정", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        box = tk.Frame(f)
        box.grid(row=1, column=0, columnspan=3, sticky="we", pady=(4, 4))
        self.sched_list = tk.Listbox(box, width=52, height=10, font=font, activestyle="none")
        sb = tk.Scrollbar(box, command=self.sched_list.yview)
        self.sched_list.config(yscrollcommand=sb.set)
        self.sched_list.pack(side="left")
        sb.pack(side="left", fill="y")
        self.sched_status = tk.Label(f, font=("Malgun Gothic", 9), fg="#666")
        self.sched_status.grid(row=2, column=0, sticky="w")
        btns = tk.Frame(f)
        btns.grid(row=2, column=1, columnspan=2, sticky="e")
        tk.Button(btns, text="새로고침", command=self.refresh_schedule).pack(side="left", padx=2)
        tk.Button(btns, text="선택한 일정 삭제", command=self.delete_selected_event).pack(side="left", padx=2)

        tk.Frame(f, height=1, bg="#ccc").grid(row=3, column=0, columnspan=3, sticky="we", pady=10)
        tk.Label(f, text="일정 추가", font=("Malgun Gothic", 10, "bold")).grid(row=4, column=0, columnspan=3, sticky="w")
        form = tk.Frame(f)
        form.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        now = datetime.now()
        start0 = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        def row(r, label, widget):
            tk.Label(form, text=label, font=font).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=3)
            widget.grid(row=r, column=1, sticky="w", pady=3)
            return widget

        title = row(0, "제목", tk.Entry(form, width=36, font=font))
        datef = tk.Frame(form)
        day = tk.Entry(datef, width=11, font=font, cursor="hand2")
        end_day = tk.Entry(datef, width=11, font=font, cursor="hand2")
        for e in (day, end_day):
            e.insert(0, f"{now:%Y-%m-%d}")
        day.pack(side="left")
        tk.Label(datef, text="~", font=font).pack(side="left", padx=4)
        end_day.pack(side="left")
        row(1, "날짜", datef)

        def after_pick_start(picked):
            # 시작일이 종료일보다 늦으면 종료일도 같은 날로
            try:
                if datetime.strptime(end_day.get().strip(), "%Y-%m-%d").date() < picked:
                    end_day.delete(0, "end")
                    end_day.insert(0, picked.isoformat())
            except ValueError:
                end_day.delete(0, "end")
                end_day.insert(0, picked.isoformat())

        def open_picker(entry, on_pick=None):
            # 칸이 포커스를 가져가 달력이 바로 닫히지 않게, 클릭 처리가 끝난 뒤 달력을 띄움
            d.after(1, lambda: DatePicker(d, entry, on_pick))
            return "break"

        day.bind("<Button-1>", lambda e: open_picker(day, after_pick_start))
        end_day.bind("<Button-1>", lambda e: open_picker(end_day))
        allday = tk.BooleanVar(value=False)
        timef = tk.Frame(form)
        start = tk.Entry(timef, width=6, font=font)
        end = tk.Entry(timef, width=6, font=font)
        start.insert(0, f"{start0:%H:%M}")
        end.insert(0, f"{start0 + timedelta(hours=1):%H:%M}")
        start.pack(side="left")
        tk.Label(timef, text="~", font=font).pack(side="left", padx=4)
        end.pack(side="left")
        tk.Checkbutton(timef, text="하루 종일", variable=allday, font=font).pack(side="left", padx=(10, 0))
        row(2, "시간", timef)
        memo = row(3, "메모", tk.Entry(form, width=36, font=font))
        # 저장 위치: Notion 팀 일정(기본) / Google 캘린더
        dest = tk.StringVar(value="notion" if self.notion.connected else "google")
        destf = tk.Frame(form)
        if self.notion.connected:
            tk.Radiobutton(destf, text="Notion 팀 일정", variable=dest, value="notion", font=font).pack(side="left")
        if self.gcal.connected:
            tk.Radiobutton(destf, text="Google 캘린더", variable=dest, value="google", font=font).pack(side="left", padx=(8, 0))
        row(4, "저장 위치", destf)
        warn = tk.Label(f, font=("Malgun Gothic", 9), fg="#d93025")
        warn.grid(row=6, column=0, columnspan=2, sticky="w")

        def submit():
            t = title.get().strip()
            if not t:
                warn.config(text="제목을 입력해 주세요.")
                return
            try:
                dd = datetime.strptime(day.get().strip(), "%Y-%m-%d").date()
                de = datetime.strptime(end_day.get().strip(), "%Y-%m-%d").date()
                st = None if allday.get() else datetime.strptime(start.get().strip(), "%H:%M").time()
                en = None if allday.get() else datetime.strptime(end.get().strip(), "%H:%M").time()
            except ValueError:
                warn.config(text="날짜는 2026-10-21, 시간은 14:00 처럼 적어 주세요.")
                return
            if de < dd:
                warn.config(text="종료일이 시작일보다 빨라요.")
                return
            if st is not None and de > dd and datetime.combine(de, en) <= datetime.combine(dd, st):
                warn.config(text="끝나는 시간이 시작 시간보다 빨라요.")
                return
            note = memo.get().strip()
            warn.config(text="")
            title.delete(0, "end")
            memo.delete(0, "end")
            if dest.get() == "notion":
                self.sched_status.config(text="Notion 팀 일정에 넣는 중...")
                self.gcal_run("insert", self.notion.add_team_event, t, dd, de, st, en, note)
            else:
                self.sched_status.config(text="Google 캘린더에 넣는 중...")
                self.gcal_run("insert", self.gcal.insert_event, t, dd, de, st, en, note)

        tk.Button(f, text="추가", width=8, command=submit).grid(row=6, column=2, sticky="e", pady=(6, 0))
        title.bind("<Return>", lambda e: submit())
        tk.Label(f, font=("Malgun Gothic", 9), fg="#666", justify="left",
                 text="제목에 '연차'를 넣으면 그날은 쉬어요.").grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))
        apply_theme(d)
        title.focus_set()
        self.refresh_schedule()

    def refresh_schedule(self):
        if self.sched_win is not None and self.sched_win.winfo_exists():
            self.sched_status.config(text="불러오는 중...")
            self.gcal_run("list", self.gather_events, 14)

    def delete_selected_event(self):
        sel = self.sched_list.curselection()
        if not sel or sel[0] >= len(self.sched_events):
            self.sched_status.config(text="지울 일정을 목록에서 골라 주세요.")
            return
        ev = self.sched_events[sel[0]]
        from tkinter import messagebox
        notion = ev.get("source") == "notion"
        if notion and not ev.get("mine"):
            self.sched_status.config(text="팀 일정은 내가 쓴 것만 지울 수 있어요.")
            return
        where = "Notion 팀 일정" if notion else "Google 캘린더"
        if messagebox.askyesno("일정 삭제", f"이 일정을 {where}에서 삭제할까요?\n\n{self.event_label(ev)}",
                               parent=self.sched_win):
            self.sched_status.config(text="삭제하는 중...")
            if notion:  # Notion 은 휴지통으로 (30일 안에 되살릴 수 있음)
                self.gcal_run("delete", self.notion.archive, ev["id"])
            else:
                self.gcal_run("delete", self.gcal.delete_event, ev["id"])
