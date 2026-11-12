"""Notion 연결과 일정·할 일·일일 보고 읽기·쓰기"""

import base64
import http.server
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta

from .constants import (
    NOTION_API,
    NOTION_CAL_DB,
    NOTION_CLIENT,
    NOTION_EMAIL,
    NOTION_PORT,
    NOTION_REDIRECT,
    NOTION_TODO_DB,
    NOTION_TOKEN,
    NOTION_VERSION,
)
from .secrets_store import load_secret, save_secret


class NotionClient:
    """Notion API (OAuth). 브라우저에서 한 번 허용하면 토큰을 암호화해 저장. 네트워크 메서드는 스레드에서 부를 것"""

    def __init__(self):
        self.token = load_secret(NOTION_TOKEN) or {}
        self.lock = threading.Lock()

    @property
    def connected(self):
        return bool(self.token.get("access_token"))

    @staticmethod
    def client():
        return load_secret(NOTION_CLIENT) or {}

    @staticmethod
    def save_client(client_id, client_secret):
        save_secret(NOTION_CLIENT, {"client_id": client_id, "client_secret": client_secret})

    def _token_request(self, body):
        c = self.client()
        basic = base64.b64encode(f"{c['client_id']}:{c['client_secret']}".encode()).decode()
        req = urllib.request.Request(f"{NOTION_API}/oauth/token", data=json.dumps(body).encode(), headers={
            "Authorization": f"Basic {basic}", "Content-Type": "application/json", "Notion-Version": NOTION_VERSION})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Notion 토큰 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from None
        self.token = {"access_token": tok["access_token"],
                      "refresh_token": tok.get("refresh_token") or self.token.get("refresh_token"),
                      "expires": time.time() + int(tok["expires_in"]) - 60 if tok.get("expires_in") else None,
                      "workspace": tok.get("workspace_name", ""), "bot_id": tok.get("bot_id", "")}
        save_secret(NOTION_TOKEN, self.token)

    def authorize(self, timeout=300):
        """브라우저로 Notion 허용 → localhost:8742/notion 으로 돌아온 코드를 토큰으로 바꿈"""
        c = self.client()
        state = secrets.token_urlsafe(16)
        got = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/notion":
                    self.send_response(404)
                    self.end_headers()
                    return
                got.update({k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()})
                ok = "code" in got and got.get("state") == state
                msg = "Notion 연결 완료! 이 창은 닫아도 돼요." if ok else "연결하지 못했어요. 앱을 확인해 주세요."
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<html><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>{msg}</body></html>".encode())

            def log_message(self, *a):
                pass

        # 브라우저가 localhost 를 IPv4(127.0.0.1)나 IPv6(::1) 어느 쪽으로 찾아와도 받도록 둘 다 엶 (이 PC 안에서만)
        servers = [http.server.HTTPServer(("127.0.0.1", NOTION_PORT), Handler)]
        try:
            class V6(http.server.HTTPServer):
                address_family = socket.AF_INET6
            servers.append(V6(("::1", NOTION_PORT), Handler))
        except OSError:
            pass
        for s in servers:
            s.timeout = 0.3
        url = f"{NOTION_API}/oauth/authorize?" + urllib.parse.urlencode({
            "client_id": c["client_id"], "response_type": "code", "owner": "user",
            "redirect_uri": NOTION_REDIRECT, "state": state})
        webbrowser.open(url)
        end = time.time() + timeout
        try:
            while time.time() < end and "code" not in got and "error" not in got:
                for s in servers:
                    s.handle_request()
        finally:
            for s in servers:
                s.server_close()
        if got.get("error"):
            raise RuntimeError(f"Notion 이 거절했어요: {got['error']}")
        if "code" not in got or got.get("state") != state:
            raise RuntimeError("시간 안에 허용하지 않았어요")
        with self.lock:
            self._token_request({"grant_type": "authorization_code", "code": got["code"],
                                 "redirect_uri": NOTION_REDIRECT})

    def call(self, method, path, body=None):
        with self.lock:
            exp = self.token.get("expires")
            if exp and time.time() >= exp and self.token.get("refresh_token"):
                self._token_request({"grant_type": "refresh_token", "refresh_token": self.token["refresh_token"]})
            access = self.token["access_token"]
        req = urllib.request.Request(f"{NOTION_API}{path}", method=method,
                                     data=json.dumps(body).encode("utf-8") if body is not None else None,
                                     headers={"Authorization": f"Bearer {access}", "Notion-Version": NOTION_VERSION,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Notion API 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from None

    def check(self):
        """연결 확인: 볼 수 있는 데이터베이스 이름들"""
        res = self.call("POST", "/search", {"filter": {"property": "object", "value": "database"}, "page_size": 50})
        names = []
        for db in res.get("results", []):
            names.append("".join(t.get("plain_text", "") for t in db.get("title", [])) or "(제목 없음)")
        return {"workspace": self.token.get("workspace", ""), "databases": names}

    # --- TODO · 일정/일일업무 데이터베이스 ---
    def me(self):
        """NOTION_EMAIL 의 Notion 사용자 ID (한 번 찾으면 저장)"""
        if self.token.get("me"):
            return self.token["me"]
        cursor = None
        for _ in range(10):
            res = self.call("GET", "/users?page_size=100" + (f"&start_cursor={cursor}" if cursor else ""))
            for u in res.get("results", []):
                if (u.get("person") or {}).get("email", "").lower() == NOTION_EMAIL.lower():
                    with self.lock:
                        self.token["me"] = u["id"]
                        save_secret(NOTION_TOKEN, self.token)
                    return u["id"]
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        raise RuntimeError(f"Notion 에서 {NOTION_EMAIL} 사용자를 찾지 못했어요")

    def query(self, db, filt=None, sorts=None, limit=300):
        out, cursor = [], None
        while len(out) < limit:
            body = {"page_size": 100}
            if filt:
                body["filter"] = filt
            if sorts:
                body["sorts"] = sorts
            if cursor:
                body["start_cursor"] = cursor
            res = self.call("POST", f"/databases/{db}/query", body)
            out += res.get("results", [])
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return out

    @staticmethod
    def _text(props, name):
        p = props.get(name, {})
        return "".join(t.get("plain_text", "") for t in p.get(p.get("type", "title"), []) or []).strip()

    @staticmethod
    def _date(props, name):
        d = (props.get(name) or {}).get("date") or {}
        return d.get("start"), d.get("end")

    @staticmethod
    def _choice(props, name):
        p = props.get(name) or {}
        v = p.get(p.get("type", "")) or {}
        return v.get("name", "") if isinstance(v, dict) else ""

    @staticmethod
    def _iso(day, t=None):
        return day.isoformat() if t is None else f"{datetime.combine(day, t):%Y-%m-%dT%H:%M:%S}+09:00"

    def my_todos(self):
        """담당자가 나이고 완료가 아닌 TODO (기한 순)"""
        pages = self.query(NOTION_TODO_DB, {"and": [
            {"property": "담당자", "people": {"contains": self.me()}},
            {"property": "상태", "status": {"does_not_equal": "완료"}}]},
            [{"property": "기한", "direction": "ascending"}])
        todos = []
        for pg in pages:
            pr = pg["properties"]
            due, _ = self._date(pr, "기한")
            todos.append({"id": pg["id"], "title": self._text(pr, "할 일") or "(제목 없음)", "due": due[:10] if due else None,
                          "status": self._choice(pr, "상태"), "category": self._choice(pr, "분류"), "url": pg.get("url")})
        return todos

    def my_done_today(self):
        """오늘 완료로 바꾼 내 TODO 제목들 (오늘 수정됐고 상태가 '완료')"""
        pages = self.query(NOTION_TODO_DB, {"and": [
            {"property": "담당자", "people": {"contains": self.me()}},
            {"property": "상태", "status": {"equals": "완료"}},
            {"timestamp": "last_edited_time", "last_edited_time": {"on_or_after": date.today().isoformat()}}]},
            limit=50)
        return [self._text(pg["properties"], "할 일") or "(제목 없음)" for pg in pages]

    def day_wrap(self):
        """퇴근 전 마무리: 오늘 끝낸 할 일, 남은 할 일, 일일 업무 상태"""
        return {"done": self.my_done_today(), "todos": self.my_todos(), "report": self.my_report_today()}

    def complete_todo(self, page_id):
        self.call("PATCH", f"/pages/{page_id}", {"properties": {"상태": {"status": {"name": "완료"}}}})
        return page_id

    def add_todo(self, title, due=None, category=None):
        props = {"할 일": {"title": [{"text": {"content": title}}]},
                 "담당자": {"people": [{"id": self.me()}]},
                 "상태": {"status": {"name": "시작 전"}}}
        if due:
            props["기한"] = {"date": {"start": due.isoformat()}}
        if category:
            props["분류"] = {"select": {"name": category}}
        return self.call("POST", "/pages", {"parent": {"database_id": NOTION_TODO_DB}, "properties": props})

    def save_todos(self, plan):
        """메모장에서 고친 할 일 반영: plan = {'update': [(id,title,due,cat)], 'add': [(title,due,cat)], 'delete': [id]}.
        지울 때는 Notion 휴지통으로 보냄 (되살릴 수 있음)"""
        for pid, title, due, cat in plan["update"]:
            props = {"할 일": {"title": [{"text": {"content": title}}]},
                     "기한": {"date": {"start": due.isoformat()} if due else None},
                     "분류": {"select": {"name": cat} if cat else None}}
            self.call("PATCH", f"/pages/{pid}", {"properties": props})
        for title, due, cat in plan["add"]:
            self.add_todo(title, due, cat)
        for pid in plan.get("done", []):
            self.complete_todo(pid)
        for pid in plan["delete"]:
            self.call("PATCH", f"/pages/{pid}", {"archived": True})
        bits = [f"{label} {len(plan.get(k, []))}개" for k, label in
                (("update", "수정"), ("add", "추가"), ("done", "완료"), ("delete", "삭제")) if plan.get(k)]
        return {"summary": ", ".join(bits) or "바뀐 게 없어요", "done": len(plan.get("done", []))}

    def _cal_items(self, kind, d0, d1, mine_only=False):
        """일정/일일업무 DB 에서 유형이 kind 이고 [d0, d1) 와 겹치는 항목. Google 일정과 같은 모양으로"""
        filt = [{"property": "유형", "select": {"equals": kind}},
                {"property": "Date", "date": {"on_or_after": (d0 - timedelta(days=31)).isoformat()}},
                {"property": "Date", "date": {"before": d1.isoformat()}}]
        if mine_only:
            filt.append({"property": "작성자", "people": {"contains": self.me()}})
        me = self.me()
        out = []
        for pg in self.query(NOTION_CAL_DB, {"and": filt}, [{"property": "Date", "direction": "ascending"}]):
            pr = pg["properties"]
            s, e = self._date(pr, "Date")
            if not s:
                continue
            all_day = len(s) == 10
            if all_day:  # Google 처럼 하루 종일 일정의 끝은 '다음 날'로
                last = date.fromisoformat((e or s)[:10])
                e = (last + timedelta(days=1)).isoformat()
                last_day = last
            else:
                e = e or s
                last_day = date.fromisoformat(e[:10])
            if last_day < d0:
                continue
            writers = [p.get("id") for p in (pr.get("작성자") or {}).get("people", [])]
            out.append({"id": pg["id"], "summary": self._text(pr, "Name") or "(제목 없음)", "all_day": all_day,
                        "start": s, "end": e, "source": "notion", "mine": me in writers,
                        "status": self._choice(pr, "Status"), "url": pg.get("url")})
        return out

    def team_events(self, d0, d1):
        return self._cal_items("일정", d0, d1)

    def my_vacation_days(self, back=120, ahead=60):
        today = date.today()
        days = set()
        for ev in self._cal_items("휴가", today - timedelta(days=back), today + timedelta(days=ahead), mine_only=True):
            d = date.fromisoformat(ev["start"][:10])
            last = date.fromisoformat(ev["end"][:10]) - (timedelta(days=1) if ev["all_day"] else timedelta(0))
            while d <= last:
                days.add(d.isoformat())
                d += timedelta(days=1)
        return days

    def my_report_today(self):
        """오늘 내 일일보고: {'exists', 'done', 'url'}"""
        today = date.today()
        items = self._cal_items("일일보고", today, today + timedelta(days=1), mine_only=True)
        items = [it for it in items if it["start"][:10] == today.isoformat()]
        if not items:
            return {"exists": False, "done": False, "url": None}
        it = items[0]
        return {"exists": True, "done": it["status"] == "Done", "url": it["url"], "id": it["id"]}

    def set_report_status(self, name):
        """오늘 내 일일보고의 Status 를 name (Done / In progress) 으로"""
        rep = self.my_report_today()
        if not rep["exists"]:
            raise RuntimeError("오늘 일일 업무 칸이 아직 없어요")
        self.call("PATCH", f"/pages/{rep['id']}", {"properties": {"Status": {"status": {"name": name}}}})
        return {"url": rep["url"], "section": "마감했어요" if name == "Done" else "마감을 취소했어요"}

    def auto_close_report(self, texts=None):
        """18:30 자동 마감: texts(창에 쓰던 글)가 있으면 먼저 저장하고, 아직 Done 이 아니면 Done 으로. 'closed' / 'skip'"""
        rep = self.my_report_today()
        if not rep["exists"] or rep["done"]:
            return "skip"
        if texts is not None:
            self.save_report(texts)
        self.set_report_status("Done")
        return "closed"

    def set_report_done(self):
        return self.set_report_status("Done")

    def read_report(self):
        """오늘 일일보고의 칸별 글머리 목록: {'exists','url','status','sections':[[{id,text}]]}"""
        rep = self.my_report_today()
        if not rep["exists"]:
            return {"exists": False}
        pid = rep["id"]
        sections, heads = self._report_sections(pid)
        status = self._choice(self.call("GET", f"/pages/{pid}")["properties"], "Status")
        out = {"exists": True, "url": rep["url"], "status": status, "sections": sections, "heads": heads, "page": pid}
        if not any(b["text"] for b in sections[0]):  # 오늘 1번 칸이 비었으면 지난 일일 업무의 '익일 업무 계획'을 가져옴
            out["carry"] = self.prev_plan()
        return out

    def _report_sections(self, pid):
        blocks, cursor = [], None
        while True:
            res = self.call("GET", f"/blocks/{pid}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else ""))
            blocks += res.get("results", [])
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        sections, heads, cur = [[], [], []], [None, None, None], None
        for b in blocks:
            text = "".join(t.get("plain_text", "") for t in b.get(b["type"], {}).get("rich_text", []))
            if b["type"] == "heading_2":
                head = text.strip()[:1]
                cur = int(head) - 1 if head in "123" and head else None
                if cur is not None:
                    heads[cur] = b["id"]
            elif b["type"] == "bulleted_list_item" and cur is not None:
                sections[cur].append({"id": b["id"], "text": text.strip()})
        return sections, heads

    def prev_plan(self):
        """오늘 이전 가장 최근 내 일일 업무의 '2. 익일 업무 계획' 줄 목록 (없으면 [])"""
        today = date.today()
        items = self._cal_items("일일보고", today - timedelta(days=14), today, mine_only=True)
        items = [it for it in items if it["start"][:10] < today.isoformat()]
        for it in sorted(items, key=lambda x: x["start"], reverse=True):
            lines = [b["text"] for b in self._report_sections(it["id"])[0][1] if b["text"]]
            if lines:
                return lines
        return []

    def save_report(self, texts):
        """메모장에서 고친 내용(칸별 줄 목록 texts[0..2])을 Notion 과 맞춤: 바뀐 줄 수정, 늘어난 줄 추가, 줄어든 줄 삭제"""
        cur = self.read_report()
        if not cur["exists"]:
            raise RuntimeError("오늘 일일 업무 칸이 아직 없어요")
        changed = 0
        for s in range(3):
            old, new = cur["sections"][s], texts[s]
            for i in range(min(len(old), len(new))):
                if old[i]["text"] != new[i]:
                    self.update_report_line(old[i]["id"], new[i])
                    changed += 1
            if len(new) > len(old):
                after = old[-1]["id"] if old else cur["heads"][s]
                rows = [{"object": "block", "type": "bulleted_list_item",
                         "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": t}}]}}
                        for t in new[len(old):]]
                self.call("PATCH", f"/blocks/{cur['page']}/children", {"after": after, "children": rows})
                changed += len(rows)
            elif len(new) < len(old):
                for k, b in enumerate(old[len(new):]):
                    if k == 0 and not new:  # 칸이 통째로 비면 템플릿처럼 빈 글머리 하나는 남김
                        if not b["text"]:
                            continue
                        self.delete_report_line(b["id"], True)
                    else:
                        self.delete_report_line(b["id"])
                    changed += 1
        return {"url": cur["url"], "section": f"저장했어요 (바뀐 줄 {changed}개)" if changed else "바뀐 게 없어요"}

    def update_report_line(self, block_id, text):
        self.call("PATCH", f"/blocks/{block_id}", {"bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}]}})
        return {"url": None, "section": "수정했어요"}

    def delete_report_line(self, block_id, keep_empty=False):
        """줄을 지움. 그 칸의 마지막 줄이면 템플릿처럼 빈 글머리 하나를 남김"""
        if keep_empty:
            self.call("PATCH", f"/blocks/{block_id}", {"bulleted_list_item": {"rich_text": []}})
        else:
            self.call("DELETE", f"/blocks/{block_id}")
        return {"url": None, "section": "지웠어요"}

    def report_write(self, section, text, done):
        """일일 업무에 한 줄 넣고(내용이 있을 때), done 이면 Status 도 Done 으로"""
        res = self.add_report_line(section, text) if text else None
        if done:
            res = self.set_report_done()
            if text:
                res["section"] = f"{self.REPORT_SECTIONS[section]}\n그리고 Status 를 Done 으로"
        return res

    REPORT_SECTIONS = ("1. 금일 업무 진행 현황", "2. 익일 업무 계획", "3. 종합 의견 및 건의")

    def add_report_line(self, section, text, dry=False):
        """오늘 내 일일보고 페이지의 section(0~2) 목록 맨 아래에 한 줄을 넣음. 빈 글머리 하나뿐이면 거기에 채움.
        dry=True 면 어디에 넣을지만 찾고 쓰지는 않음"""
        rep = self.my_report_today()
        if not rep["exists"]:
            raise RuntimeError("오늘 일일 업무 칸이 아직 없어요")
        pid, blocks, cursor = rep["id"], [], None
        while True:
            res = self.call("GET", f"/blocks/{pid}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else ""))
            blocks += res.get("results", [])
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")

        def plain(b):
            return "".join(t.get("plain_text", "") for t in b.get(b["type"], {}).get("rich_text", []))
        heads = [i for i, b in enumerate(blocks) if b["type"] == "heading_2"]
        start = next((i for i in heads if plain(blocks[i]).strip().startswith(f"{section + 1}.")), None)
        if start is None:
            raise RuntimeError(f"일일 업무 페이지에서 '{self.REPORT_SECTIONS[section]}' 칸을 못 찾았어요")
        end = next((i for i in heads if i > start), len(blocks))
        bullets = [b for b in blocks[start + 1:end] if b["type"] == "bulleted_list_item"]
        rich = [{"type": "text", "text": {"content": text}}]
        if bullets and not plain(bullets[-1]).strip():  # 비어 있는 마지막 글머리에 채움
            plan = ("fill", bullets[-1]["id"])
        elif bullets:
            plan = ("after", bullets[-1]["id"])
        else:
            plan = ("after", blocks[start]["id"])
        if dry:
            return plan
        if plan[0] == "fill":
            self.call("PATCH", f"/blocks/{plan[1]}", {"bulleted_list_item": {"rich_text": rich}})
        else:
            self.call("PATCH", f"/blocks/{pid}/children", {"after": plan[1], "children": [
                {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich}}]})
        return {"url": rep["url"], "section": self.REPORT_SECTIONS[section]}

    def add_team_event(self, title, d0, d1=None, t0=None, t1=None, memo=""):
        d1 = d1 or d0
        date_v = {"start": self._iso(d0, t0)}
        if t0 is None:
            if d1 != d0:
                date_v["end"] = d1.isoformat()
        else:
            date_v["end"] = self._iso(d1, t1 or t0)
        body = {"parent": {"database_id": NOTION_CAL_DB}, "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Date": {"date": date_v},
            "유형": {"select": {"name": "일정"}},
            "작성자": {"people": [{"id": self.me()}]}}}
        if memo:
            body["children"] = [{"object": "block", "type": "paragraph",
                                 "paragraph": {"rich_text": [{"type": "text", "text": {"content": memo}}]}}]
        res = self.call("POST", "/pages", body)
        return {"summary": title, "url": res.get("url")}

    def archive(self, page_id):
        self.call("PATCH", f"/pages/{page_id}", {"archived": True})
        return page_id

    def disconnect(self):
        self.token = {}
        for f in (NOTION_TOKEN,):
            try:
                os.remove(f)
            except OSError:
                pass
