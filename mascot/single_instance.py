"""프로그램이 두 번 켜지지 않게 막고, 두 번째로 켜면 이미 켜진 쪽에 알림"""

import ctypes
from ctypes import wintypes


SINGLE_MUTEX = "Local\\namolppaemi_single_instance"  # 이 이름의 잠금을 가진 나몰빼미가 있으면 또 켜지지 않음
WAKE_EVENT = "Local\\namolppaemi_wake"               # 두 번째로 켜려고 하면 이미 켜진 나몰빼미에게 알림


def already_running():
    """이미 켜진 나몰빼미가 있으면 그쪽에 '누가 또 켰어요' 신호를 보내고 True.
    없으면 잠금을 잡고 False (잠금은 이 프로그램이 꺼질 때 Windows 가 알아서 풂)"""
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateEventW.restype = wintypes.HANDLE
    k32.OpenEventW.restype = wintypes.HANDLE
    global _single_mutex
    _single_mutex = k32.CreateMutexW(None, False, SINGLE_MUTEX)
    if k32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS 가 아니면 처음 켜진 것
        return False
    ev = k32.OpenEventW(0x0002, False, WAKE_EVENT)  # EVENT_MODIFY_STATE
    if ev:
        k32.SetEvent(ev)
        k32.CloseHandle(ev)
    return True
