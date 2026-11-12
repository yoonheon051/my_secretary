"""토큰·비밀번호를 Windows DPAPI 로 암호화해 저장·읽기"""

import ctypes
import json
from ctypes import wintypes

from .constants import MAIL_CFG


# ---------- Gmail 알림 ----------
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data, protect):
    """Windows DPAPI: 현재 Windows 사용자 계정에서만 풀 수 있게 암호화/복호화"""
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI 실패")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def save_mail_cfg(addr, password):
    raw = json.dumps({"addr": addr, "password": password}).encode("utf-8")
    with open(MAIL_CFG, "wb") as fp:
        fp.write(_dpapi(raw, True))


def load_mail_cfg():
    try:
        with open(MAIL_CFG, "rb") as fp:
            d = json.loads(_dpapi(fp.read(), False).decode("utf-8"))
        return d["addr"], d["password"]
    except (OSError, ValueError, KeyError):
        return None


# ---------- 휴일 (Google 캘린더) ----------
def save_secret(path, data):
    with open(path, "wb") as fp:
        fp.write(_dpapi(json.dumps(data).encode("utf-8"), True))


def load_secret(path):
    try:
        with open(path, "rb") as fp:
            return json.loads(_dpapi(fp.read(), False).decode("utf-8"))
    except (OSError, ValueError):
        return None
