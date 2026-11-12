"""Windows 화면·창 도구: 모니터 영역, 다른 앱 창 찾기, 항상 위 순서, 입력 유휴 시간, 전역 단축키"""

import ctypes
import os
import threading
from ctypes import wintypes

from .constants import HOTKEYS


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long)]


def work_area():
    """주 모니터에서 작업 표시줄을 뺀 화면 영역 (left, top, right, bottom)"""
    r = RECT()
    try:
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            return r.l, r.t, r.r, r.b
    except Exception:
        pass
    return None


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


def monitor_areas():
    """모니터마다 작업 표시줄을 뺀 영역 [(left, top, right, bottom, 주 모니터인지)]. 실패하면 주 모니터만"""
    out = []
    try:
        proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC,
                                  ctypes.POINTER(RECT), wintypes.LPARAM)

        def cb(hmon, hdc, rect, lp):
            info = MONITORINFO(ctypes.sizeof(MONITORINFO))
            if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                w = info.rcWork
                out.append((w.l, w.t, w.r, w.b, bool(info.dwFlags & 1)))
            return True

        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    except Exception:
        out = []
    if not out:
        a = work_area()
        out = [(*a, True)] if a else []
    return out


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    """마지막으로 마우스·키보드를 건드린 뒤 지난 시간(초). 알 수 없으면 0"""
    try:
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000
    except Exception:
        pass
    return 0.0


class HotkeyListener(threading.Thread):
    """어디서든 누르는 단축키(Ctrl+Alt+글자)를 Windows 에 등록하고, 눌리면 out 큐에 이름을 넣음.
    RegisterHotKey 는 메시지를 받는 스레드에서 해야 해서 따로 스레드를 둠. 다른 프로그램이 이미 쓰는 조합이면 실패 목록에 넣음"""

    def __init__(self, out):
        super().__init__(daemon=True)
        self.out = out
        self.failed = []

    def run(self):
        u32 = ctypes.windll.user32
        names = {}
        for hid, (key, name) in HOTKEYS.items():
            # MOD_ALT | MOD_CONTROL | MOD_NOREPEAT
            if u32.RegisterHotKey(None, hid, 0x0001 | 0x0002 | 0x4000, ord(key)):
                names[hid] = name
            else:
                self.failed.append(f"Ctrl+Alt+{key}")
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312 and msg.wParam in names:  # WM_HOTKEY
                self.out.put(names[msg.wParam])


def toplevel_hwnd(win):
    """tkinter 창의 실제 Windows 창 핸들"""
    return ctypes.windll.user32.GetParent(win.winfo_id())


def raise_in_order(wins):
    """'항상 위' 창들을 주어진 순서대로 쌓음. 마지막 창이 맨 앞에 보임"""
    for w in wins:
        try:
            # HWND_TOPMOST, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            ctypes.windll.user32.SetWindowPos(toplevel_hwnd(w), wintypes.HWND(-1), 0, 0, 0, 0, 0x13)
        except Exception:
            pass


# ---------- 다른 앱 창 위에 서기 ----------
try:
    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    user32.GetParent.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.GetWindowLongW.restype = ctypes.c_long
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
except Exception:
    user32 = None


def win_rect(hwnd):
    """보이는 창이면 화면에 실제로 보이는 테두리 (l, t, r, b), 아니면 None"""
    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return None
    r = RECT()
    # DWMWA_EXTENDED_FRAME_BOUNDS: 보이지 않는 크기조절 테두리를 뺀 실제 창 영역
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.l, r.t, r.r, r.b


def list_windows():
    """위에서부터 아래 순서(z-order)로 화면에 보이는 앱 창 목록 [(hwnd, l, t, r, b, 최대화)]"""
    own_pid = os.getpid()
    wins = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
        cloaked = ctypes.c_int(0)  # 다른 가상 데스크톱 등에 숨겨진 창
        dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        if user32.GetWindowLongW(hwnd, -20) & 0x80:  # WS_EX_TOOLWINDOW
            return True
        if user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        rect = win_rect(hwnd)
        if rect:
            wins.append((hwnd, *rect, bool(user32.IsZoomed(hwnd))))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return wins


def process_exe(hwnd):
    """창을 만든 프로그램의 실행 파일 이름 (소문자, 예: 'claude.exe'). 모르면 ''"""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(len(buf))
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def find_claude_window():
    """Claude 데스크톱 앱 창 (없으면 제목에 'Claude Code' 가 들어간 터미널 창). 최소화된 창도 찾음"""
    app, term = [], []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowLongW(hwnd, -20) & 0x80:  # 툴 창 제외
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if process_exe(hwnd) == "claude.exe":
            app.append(hwnd)
        elif "claude code" in buf.value.lower():
            term.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return (app or term or [None])[0]


def find_app_window(exe):
    """그 프로그램(예: 'slack.exe')의 보이는 창 (최소화된 창도). 없으면 None"""
    found = []

    def cb(hwnd, _):
        if (user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd)
                and not user32.GetWindowLongW(hwnd, -20) & 0x80 and process_exe(hwnd) == exe):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found[0] if found else None


def bring_to_front(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)


def find_platforms(area):
    """올라설 수 있는 창 윗변 구간 [(hwnd, 왼쪽, 오른쪽, y)]. 더 위에 있는 창에 가려진 부분은 뺌."""
    left, top, right, bottom = area
    wins = list_windows()
    plats = []
    for i, (hwnd, l, t, r, b, zoomed) in enumerate(wins):
        if zoomed or r - l < 120 or t < top + 60 or t > bottom - 20:
            continue
        segs = [(max(l, left), min(r, right))]
        for _, l2, t2, r2, b2, _z in wins[:i]:
            if t2 <= t <= b2:
                segs = [s for a, z in segs
                        for s in ((a, min(z, l2)), (max(a, r2), z)) if s[1] > s[0]]
        plats += [(hwnd, a, z, t) for a, z in segs if z - a >= 60]
    return plats
