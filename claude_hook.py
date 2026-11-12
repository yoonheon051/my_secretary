"""Claude Code 훅 → 나몰빼미 연결

~/.claude/settings.json 의 훅이 이 스크립트를 부름:  pythonw claude_hook.py <이벤트>
Claude Code 가 넘겨주는 JSON(stdin)을 읽어서 상태 파일에 세션 상태와 최근 이벤트를 적음.
작업 시작은 UserPromptSubmit(메시지 보냄)과 PreToolUse(도구 사용) 중 먼저 오는 것으로 봄.
나몰빼미는 이 파일이 바뀌었는지만 보고 반응함 (고민하는 모습 / 작업 끝 알림 / 확인 대기 알림).

상태 파일은 OneDrive 밖(%LOCALAPPDATA%\\namolppaemi)에 둠: 동기화가 파일을 잡고 있으면 덮어쓰기가 실패해서.
"""
import json
import os
import sys
import time

DATA = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "namolppaemi")
STATUS = os.path.join(DATA, "claude_status.json")
LOG = os.path.join(DATA, "claude_hook.log")  # 훅이 불린 기록 (문제 확인용, 커지면 비움)
KEEP_EVENTS = 20
STALE_SEC = 6 * 3600  # 이만큼 소식 없는 세션은 지움 (Stop 없이 꺼진 세션)


def log(*parts):
    """기록 한 줄을 버퍼 없이 바로 씀 (중간에 끊겨도 어디까지 왔는지 남게)"""
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 64 * 1024:
            os.remove(LOG)
        line = f"{time.strftime('%m-%d %H:%M:%S')} " + " ".join(str(p) for p in parts) + "\n"
        fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def save(st):
    """내용을 다 만든 뒤 임시 파일에 한 번에 쓰고 바꿔 끼움. 나몰빼미가 읽는 중이면 잠깐 기다렸다 다시"""
    text = json.dumps(st, ensure_ascii=False)
    tmp = f"{STATUS}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        fp.write(text)
    for _ in range(20):
        try:
            os.replace(tmp, STATUS)
            return
        except PermissionError:
            time.sleep(0.05)
    os.remove(tmp)


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    os.makedirs(DATA, exist_ok=True)
    try:
        # Claude Code 는 UTF-8 로 넘겨주는데 Windows 기본(CP949)으로 읽으면 한글 경로가 깨져서 바이트로 읽음
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except (ValueError, OSError, AttributeError) as e:
        log("stdin-error", event, repr(e)[:80])
        data = {}
    sid = str(data.get("session_id") or "unknown")
    cwd = data.get("cwd") or ""
    now = time.time()
    log(event, sid[:8], os.path.basename(cwd))
    try:
        with open(STATUS, encoding="utf-8") as fp:
            st = json.load(fp)
    except (OSError, ValueError):
        st = {}
    sessions = {k: v for k, v in st.get("sessions", {}).items() if now - v.get("t", 0) < STALE_SEC}
    events = st.get("events", [])

    if event in ("UserPromptSubmit", "PreToolUse"):
        cur = sessions.get(sid)
        if cur and cur.get("state") == "working" and now - cur.get("t", 0) < 60:
            return  # 이미 작업 중으로 적혀 있으면 다시 쓰지 않음 (도구를 쓸 때마다 불리므로)
        sessions[sid] = {"state": "working", "t": now, "cwd": cwd}
    elif event in ("Stop", "SessionEnd"):
        sessions.pop(sid, None)
        recent = [e for e in events if e.get("sid") == sid and e.get("kind") == "done" and now - e["t"] < 3]
        if event == "Stop" and not recent:  # 응답이 끝날 때마다 알림 (같은 세션에서 3초 안에 겹치면 한 번만)
            events.append({"kind": "done", "sid": sid, "cwd": cwd, "t": now})
    elif event == "Notification":
        kind = data.get("notification_type") or ""
        if kind != "idle_prompt":  # '입력 기다리는 중' 알림은 Stop 알림과 겹쳐서 뺌
            events.append({"kind": "waiting", "sid": sid, "cwd": cwd, "t": now,
                           "message": str(data.get("message") or "")[:120]})
        if sid in sessions:
            sessions[sid]["t"] = now
    else:
        return
    save({"sessions": sessions, "events": events[-KEEP_EVENTS:]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 훅이 실패해도 Claude 작업은 그대로 진행되게 (원인만 기록)
        log("error", repr(e)[:150])
