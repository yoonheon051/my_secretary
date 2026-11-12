"""Slack 알림(DM·멘션) 확인"""

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .constants import SLACK_DM_ACTIVE_DAYS, SLACK_DM_REFRESH_SEC, SLACK_POLL_SEC


def slack_api(token, method, **params):
    """Slack Web API 호출. 너무 자주 불러서 429(속도 제한)가 오면 알려 준 시간만큼 기다렸다 다시 (최대 3번)"""
    req = urllib.request.Request(f"https://slack.com/api/{method}?" + urllib.parse.urlencode(params),
                                 headers={"Authorization": f"Bearer {token}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(min(60, int(e.headers.get("Retry-After") or 5)))
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Slack 오류"))
    return data


class SlackChecker(threading.Thread):
    """백그라운드에서 1분마다 '나를 멘션한 글'과 'DM' 중 새로 온 것을 찾음 (읽음 처리하지 않음).
    out 큐로 ("new", [(종류, 보낸 사람, 내용, 채널 ID)]), ("ok", 내 정보), ("err", 메시지) 를 넘김"""

    def __init__(self, token, out):
        super().__init__(daemon=True)
        self.token, self.out = token, out
        self.stop_evt = threading.Event()
        self.me = self.team = None
        self.since = time.time()  # 켠 뒤에 온 것만 알림
        self.names = {}
        self.dms, self.dms_at = [], 0.0

    def api(self, method, **params):
        return slack_api(self.token, method, **params)

    def name(self, uid):
        if uid not in self.names:
            try:
                u = self.api("users.info", user=uid)["user"]
                p = u.get("profile", {})
                self.names[uid] = p.get("display_name") or p.get("real_name") or u.get("name") or uid
            except Exception:
                self.names[uid] = uid
        return self.names[uid]

    def clean(self, text):
        """<@U123> → @이름 (나를 부른 멘션은 뺌), <https://...|글자> → 글자, 줄바꿈 → 공백"""
        text = re.sub(r"<@(\w+)>", lambda m: "" if m.group(1) == self.me else "@" + self.name(m.group(1)),
                      text or "")
        text = re.sub(r"<[^|>]+\|([^>]+)>", r"\1", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        return " ".join(text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").split())

    def active_dms(self):
        """최근 SLACK_DM_ACTIVE_DAYS 일 안에 대화가 있었던 DM·그룹 DM 방 ID (가끔만 다시 읽음)"""
        if time.time() - self.dms_at < SLACK_DM_REFRESH_SEC:
            return self.dms
        chans, cursor = [], None
        while True:
            params = {"types": "im,mpim", "exclude_archived": "true", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            res = self.api("users.conversations", **params)
            chans += [c["id"] for c in res.get("channels", [])]
            cursor = (res.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
        oldest = time.time() - SLACK_DM_ACTIVE_DAYS * 86400
        active = []
        for cid in chans[:150]:
            msgs = self.api("conversations.history", channel=cid, limit=1).get("messages", [])
            if msgs and float(msgs[0].get("ts", 0)) >= oldest:
                active.append(cid)
        self.dms, self.dms_at = active, time.time()
        return active

    def check(self):
        if self.me is None:
            info = self.api("auth.test")
            self.me, self.team = info["user_id"], info.get("team_id")
            self.out.put(("ok", {"team": info.get("team", ""), "user": info.get("user", "")}))
        found, newest = [], self.since
        # 나를 멘션한 글 (채널·스레드)
        res = self.api("search.messages", query=f"<@{self.me}>", sort="timestamp", sort_dir="desc", count=20)
        for m in (res.get("messages") or {}).get("matches", []):
            ts = float(m.get("ts", 0))
            ch = m.get("channel") or {}
            if ts > self.since and m.get("user") != self.me and not (ch.get("is_im") or ch.get("is_mpim")):
                found.append((ts, "멘션", self.name(m.get("user", "")), self.clean(m.get("text")), ch.get("id")))
                newest = max(newest, ts)
        # DM·그룹 DM
        for cid in self.active_dms():
            res = self.api("conversations.history", channel=cid, oldest=f"{self.since:.6f}", limit=10)
            for m in res.get("messages", []):
                ts = float(m.get("ts", 0))
                if ts > self.since and m.get("user") not in (None, self.me) and not m.get("subtype"):
                    found.append((ts, "DM", self.name(m["user"]), self.clean(m.get("text")), cid))
                    newest = max(newest, ts)
        self.since = newest
        return [f[1:] for f in sorted(found)]

    def run(self):
        while not self.stop_evt.is_set():
            try:
                new = self.check()
                if new and not self.stop_evt.is_set():
                    self.out.put(("new", new))
            except Exception as e:
                if not self.stop_evt.is_set():
                    self.out.put(("err", str(e)))
            self.stop_evt.wait(SLACK_POLL_SEC)
