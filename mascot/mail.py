"""Gmail(IMAP) 알림 확인, 오전 브리핑 메일·휴가 일정 찾기"""

import email
import imaplib
import re
import threading
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr

from .constants import MAIL_POLL_SEC, VACATION_MARK


BRIEF_MARK = "[NAMOL-BRIEF]"  # 오전 브리핑 루틴이 보내는 알림 메일 제목에 들어가는 표시
IMAP_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
BRIEF_URL_RE = re.compile(r"https://claude\.ai/(?:code/)?artifact/[\w-]+")


def all_mail_box(m):
    """Gmail '전체보관함' 폴더 이름 (언어 설정에 따라 이름이 달라서 \\All 표시로 찾음). 없으면 None"""
    try:
        _, lines = m.list()
    except Exception:
        return None
    for raw in lines or []:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        found = re.match(r'\((?P<flags>[^)]*)\) "[^"]*" (?P<name>.+)$', line)
        if found and "\\All" in found.group("flags"):
            return found.group("name")
    return None


def mail_texts(msg):
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            try:
                yield part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue


def find_vacations(msg):
    """브리핑 알림 메일의 'NAMOL-연차: 2026-11-02, 2026-11-10' 줄에서 날짜들. 줄이 없으면 None ('없음'이면 빈 집합)"""
    for text in mail_texts(msg):
        for line in re.split(r"[\r\n]|<br\s*/?>", text):
            if VACATION_MARK in line:
                return set(re.findall(r"\d{4}-\d{2}-\d{2}", line.split(VACATION_MARK, 1)[1]))
    return None


def find_brief_url(msg):
    """메일 본문에서 오전 브리핑(claude.ai 아티팩트) 링크 찾기"""
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            try:
                text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue
            found = BRIEF_URL_RE.search(text)
            if found:
                return found.group(0)
    return None


def _decode(value):
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return value or ""


class MailChecker(threading.Thread):
    """백그라운드에서 받은편지함의 안 읽은 메일을 확인 (읽음 처리하지 않음).
    예외: 오전 브리핑 알림 메일([NAMOL-BRIEF], 나 → 나)만 읽음 + 보관 처리하고, 7일 지난 것은 휴지통으로"""

    def __init__(self, addr, password, out):
        super().__init__(daemon=True)
        self.addr, self.password, self.out = addr, password.replace(" ", ""), out
        self.stop_evt = threading.Event()
        self.archived = 0  # 보관 처리한 브리핑 알림 메일 수 (확인용)
        self.trashed = 0   # 휴지통으로 보낸 오래된 브리핑 알림 메일 수 (확인용)

    def run(self):
        while not self.stop_evt.is_set():
            try:
                result = self.check()
                if not self.stop_evt.is_set():
                    self.out.put(("ok", result))
            except imaplib.IMAP4.error as e:
                if not self.stop_evt.is_set():
                    self.out.put(("auth", str(e)))
                return
            except Exception as e:  # 네트워크 끊김 등: 다음 주기에 다시 시도
                if not self.stop_evt.is_set():
                    self.out.put(("err", str(e)))
            self.stop_evt.wait(MAIL_POLL_SEC)

    def check(self):
        with imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=20) as m:
            m.login(self.addr, self.password)
            # 오전 브리핑 알림 메일 (최근 7일). 읽고 보관 처리해도 찾을 수 있게 '전체보관함'에서 찾음
            since = date.today() - timedelta(days=7)
            since_s = f"{since.day:02d}-{IMAP_MONTHS[since.month - 1]}-{since.year}"
            brief_query = ("SUBJECT", f'"{BRIEF_MARK}"', "SINCE", since_s)
            brief = None
            all_box = all_mail_box(m)
            m.select(all_box or "INBOX", readonly=not all_box)
            _, data = m.uid("search", None, *brief_query)
            found = data[0].split() if data and data[0] else []
            # 내가 나에게 보낸 브리핑 알림 메일은 읽음 + 보관(받은편지함 라벨 떼기)해서 받은편지함에 안 쌓이게 함.
            # Gmail 은 전체보관함에서만 '받은편지함' 라벨을 뗄 수 있음. 보관해도 여기(전체보관함)서 계속 찾을 수 있음
            if all_box:
                _, data = m.uid("search", None, *brief_query, "FROM", f'"{self.addr}"', "X-GM-RAW", '"in:inbox"')
                mine = data[0].split() if data and data[0] else []
                if mine:
                    ids = b",".join(mine).decode()
                    m.uid("store", ids, "+FLAGS", "(\\Seen)")
                    m.uid("store", ids, "-X-GM-LABELS", "(\\Inbox)")
                    self.archived += len(mine)
                # 오래된 브리핑 알림 메일(나 → 나)은 휴지통으로 (보낸편지함에 쌓이지 않게). 휴지통에서 30일간은 되살릴 수 있음
                old_s = f"{since.day:02d}-{IMAP_MONTHS[since.month - 1]}-{since.year}"
                _, data = m.uid("search", None, "SUBJECT", f'"{BRIEF_MARK}"', "BEFORE", old_s, "FROM", f'"{self.addr}"')
                old = data[0].split() if data and data[0] else []
                if old:
                    m.uid("store", b",".join(old).decode(), "+X-GM-LABELS", "(\\Trash)")
                    self.trashed += len(old)
            if found:
                uid = found[-1]
                _, msg = m.uid("fetch", uid, "(BODY.PEEK[])")
                part = next((p for p in msg if isinstance(p, tuple)), None)
                mail_msg = email.message_from_bytes(part[1]) if part else None
                url = find_brief_url(mail_msg) if mail_msg else None
                if url:
                    brief = (uid.decode(), url, find_vacations(mail_msg))
            # 받은편지함: 브리핑 알림 메일은 일반 '메일 왔어요' 알림에서 뺌
            m.select("INBOX", readonly=True)
            _, data = m.uid("search", None, *brief_query)
            brief_uids = data[0].split() if data and data[0] else []
            _, data = m.uid("search", None, "UNSEEN")
            uids = [u for u in (data[0].split() if data and data[0] else []) if u not in brief_uids]
            recent = []
            for uid in reversed(uids[-3:]):
                _, msg = m.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                part = next((p for p in msg if isinstance(p, tuple)), None)
                if part is None:
                    continue
                head = email.message_from_bytes(part[1])
                name, addr = parseaddr(_decode(head.get("From")))
                recent.append((name or addr, _decode(head.get("Subject")) or "(제목 없음)"))
            return [u.decode() for u in uids], recent, brief
