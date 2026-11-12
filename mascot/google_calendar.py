"""Google 캘린더 연결과 일정 읽기·쓰기"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta

from .constants import GCAL_CLIENT, GCAL_EVENTS, GCAL_SCOPE, GCAL_TOKEN
from .secrets_store import load_secret, save_secret


class GoogleCalendar:
    """Google Calendar API. 처음 한 번 브라우저에서 허용하면 토큰을 암호화해 저장해 두고 계속 씀.
    네트워크를 쓰는 메서드는 오래 걸릴 수 있으니 스레드에서 부를 것."""

    def __init__(self):
        self.token = load_secret(GCAL_TOKEN) or {}
        self.lock = threading.Lock()

    @staticmethod
    def has_client():
        return os.path.exists(GCAL_CLIENT)

    @property
    def connected(self):
        return bool(self.token.get("refresh_token"))

    @staticmethod
    def _client():
        with open(GCAL_CLIENT, encoding="utf-8") as fp:
            d = json.load(fp)
        return d.get("installed") or d.get("web") or d

    @staticmethod
    def _post_form(url, data):
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _save(self, tok):
        self.token = {"refresh_token": tok.get("refresh_token") or self.token.get("refresh_token"),
                      "access_token": tok["access_token"],
                      "expires": time.time() + int(tok.get("expires_in", 3600)) - 60}
        save_secret(GCAL_TOKEN, self.token)

    def authorize(self, timeout=300):
        """브라우저로 Google 로그인·허용 → 이 PC의 임시 주소(127.0.0.1)로 돌아온 코드를 토큰으로 바꿈 (PKCE)"""
        c = self._client()
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        got = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                got.update({k: v[0] for k, v in q.items()})
                ok = "code" in got and got.get("state") == state
                msg = "Google 캘린더 연결 완료! 이 창은 닫아도 돼요." if ok else "연결하지 못했어요. 앱을 확인해 주세요."
                body = f"<html><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>{msg}</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}"
        url = c.get("auth_uri", "https://accounts.google.com/o/oauth2/auth") + "?" + urllib.parse.urlencode({
            "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": GCAL_SCOPE,
            "access_type": "offline", "prompt": "consent", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256"})
        webbrowser.open(url)
        end = time.time() + timeout
        try:
            while time.time() < end and "code" not in got and "error" not in got:
                server.handle_request()
        finally:
            server.server_close()
        if got.get("error"):
            raise RuntimeError(f"Google 이 거절했어요: {got['error']}")
        if "code" not in got or got.get("state") != state:
            raise RuntimeError("시간 안에 허용하지 않았어요")
        tok = self._post_form(c.get("token_uri", "https://oauth2.googleapis.com/token"), {
            "code": got["code"], "client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
            "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier})
        with self.lock:
            self._save(tok)

    def _access_token(self, force=False):
        with self.lock:
            if force or time.time() >= self.token.get("expires", 0):
                c = self._client()
                tok = self._post_form(c.get("token_uri", "https://oauth2.googleapis.com/token"), {
                    "client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                    "refresh_token": self.token["refresh_token"], "grant_type": "refresh_token"})
                self._save(tok)
            return self.token["access_token"]

    def _call(self, method, url, params=None, body=None):
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in (0, 1):
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self._access_token(force=attempt == 1)}",
                "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    raw = resp.read()
                    return json.loads(raw.decode("utf-8")) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    continue  # 토큰이 만료됐으면 새로 받아서 한 번 더
                detail = e.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(f"Google Calendar API 오류 {e.code}: {detail}") from None

    @staticmethod
    def _rfc3339(d):
        return f"{d:%Y-%m-%d}T00:00:00+09:00"

    def find_days(self, keyword="연차", back=120, ahead=60):
        """제목에 keyword 가 들어간 일정이 걸친 날짜들 {'YYYY-MM-DD'} (오늘 기준 back 일 전 ~ ahead 일 뒤)"""
        today = date.today()
        params = {"timeMin": self._rfc3339(today - timedelta(days=back)),
                  "timeMax": self._rfc3339(today + timedelta(days=ahead)),
                  "q": keyword, "singleEvents": "true", "maxResults": 250, "orderBy": "startTime"}
        days = set()
        for _ in range(5):  # 쪽 나눔
            res = self._call("GET", GCAL_EVENTS, params)
            for ev in res.get("items", []):
                if keyword not in ev.get("summary", ""):
                    continue
                s, e = ev.get("start", {}), ev.get("end", {})
                if "date" in s:  # 하루 종일 (끝 날짜는 다음 날로 적혀 있음)
                    d0 = date.fromisoformat(s["date"])
                    d1 = date.fromisoformat(e.get("date", s["date"])) - timedelta(days=1)
                else:
                    d0 = date.fromisoformat(s.get("dateTime", "")[:10])
                    d1 = date.fromisoformat(e.get("dateTime", s.get("dateTime", ""))[:10])
                d = d0
                while d <= max(d0, d1):
                    days.add(d.isoformat())
                    d += timedelta(days=1)
            if not res.get("nextPageToken"):
                break
            params["pageToken"] = res["nextPageToken"]
        return days

    def list_events(self, days=14):
        """오늘부터 days 일 동안의 일정 [{id, summary, start, end, all_day}] (시간 순)"""
        today = date.today()
        params = {"timeMin": self._rfc3339(today), "timeMax": self._rfc3339(today + timedelta(days=days)),
                  "singleEvents": "true", "orderBy": "startTime", "maxResults": 250}
        out = []
        res = self._call("GET", GCAL_EVENTS, params)
        for ev in res.get("items", []):
            s, e = ev.get("start", {}), ev.get("end", {})
            all_day = "date" in s
            out.append({"id": ev.get("id"), "summary": ev.get("summary", "(제목 없음)"), "all_day": all_day,
                        "start": s.get("date") or s.get("dateTime", ""), "end": e.get("date") or e.get("dateTime", "")})
        return out

    def delete_event(self, event_id):
        self._call("DELETE", f"{GCAL_EVENTS}/{urllib.parse.quote(event_id)}")
        return event_id

    def insert_event(self, title, day, end_day=None, start=None, end=None, details=""):
        """day~end_day 일정. start(시각)가 None 이면 하루 종일(종료일 포함)"""
        end_day = end_day or day
        if start is None:
            when = ({"date": day.isoformat()}, {"date": (end_day + timedelta(days=1)).isoformat()})
        else:
            s = datetime.combine(day, start)
            e = datetime.combine(end_day, end) if end else s + timedelta(hours=1)
            if e <= s and end_day == day:
                e += timedelta(days=1)  # 같은 날인데 끝 시각이 더 이르면 다음 날 새벽까지
            when = ({"dateTime": f"{s:%Y-%m-%dT%H:%M:%S}", "timeZone": "Asia/Seoul"},
                    {"dateTime": f"{e:%Y-%m-%dT%H:%M:%S}", "timeZone": "Asia/Seoul"})
        body = {"summary": title, "start": when[0], "end": when[1]}
        if details:
            body["description"] = details
        return self._call("POST", GCAL_EVENTS, body=body)

    def disconnect(self):
        tok = self.token.get("refresh_token")
        if tok:
            try:  # Google 쪽 허용도 취소
                self._post_form("https://oauth2.googleapis.com/revoke", {"token": tok})
            except Exception:
                pass
        self.token = {}
        try:
            os.remove(GCAL_TOKEN)
        except OSError:
            pass
