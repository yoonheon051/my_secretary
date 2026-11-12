"""Claude Code 작업 상태 표시"""

import json
import os
import random

from ..constants import CLAUDE_CHECK_SEC, CLAUDE_STALE_SEC, CLAUDE_STATUS


class ClaudeLinkMixin:
    # ---------- Claude Code 연동 ----------
    def update_claude(self, now):
        """claude_status.json 이 바뀌었으면 읽어서: 작업 중이면 고민하는 모습, 끝나거나 확인을 기다리면 알림"""
        if now - self.last_claude_check < CLAUDE_CHECK_SEC:
            return
        self.last_claude_check = now
        try:
            mtime = os.stat(CLAUDE_STATUS).st_mtime
        except OSError:
            self.claude_busy = False
            return
        if mtime == self.claude_mtime:
            return
        self.claude_mtime = mtime
        try:
            with open(CLAUDE_STATUS, encoding="utf-8") as fp:
                st = json.load(fp)
        except (OSError, ValueError):
            return  # 훅이 쓰는 중이면 다음에 다시
        busy = any(s.get("state") == "working" and now - s.get("t", 0) < CLAUDE_STALE_SEC
                   for s in st.get("sessions", {}).values())
        if busy and not self.claude_busy and self.state == "sleep":
            self.set_state("idle", random.uniform(3, 6))  # 졸다가도 깨서 같이 고민
        self.claude_busy = busy
        new = [e for e in st.get("events", []) if e.get("t", 0) > self.claude_seen_t]
        if not new:
            return
        self.claude_seen_t = max(e["t"] for e in new)
        last = new[-1]
        where = os.path.basename(str(last.get("cwd", "")).rstrip("\\/"))
        where = f"\n({where})" if where else ""
        hint = "\n(누르면 Claude 창을 띄워요)"
        if last["kind"] == "waiting":
            secs = 12
            self.say(f"클로드가 확인을 기다려요!{where}{hint}", secs)
        else:
            secs = 10
            done = sum(1 for e in new if e["kind"] == "done")
            more = f" ({done}개)" if done > 1 else ""
            self.say(f"클로드 작업이 끝났어요!{more}{where}{hint}", secs)
            if self.state in ("idle", "walk", "sleep", "home", "land") and self.pomo_phase != "focus":
                self.set_state("happy", 1.5)
        self.claude_notice_until = now + secs  # 이 동안 말풍선이나 나몰빼미를 누르면 Claude 창
