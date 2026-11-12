"""퇴근길 날씨 (Open-Meteo) 내려받기"""

import json
import threading

from .constants import RAIN_URL, WEATHER_HOURS, WEATHER_URL
from .holidays import fetch_text


# WMO 날씨 코드 → 한국어 (숫자가 클수록 대체로 궂은 날씨)
WMO_KO = {0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림", 45: "안개", 48: "짙은 안개",
          51: "약한 이슬비", 53: "이슬비", 55: "강한 이슬비", 56: "어는 이슬비", 57: "어는 이슬비",
          61: "약한 비", 63: "비", 65: "강한 비", 66: "어는 비", 67: "어는 비",
          71: "약한 눈", 73: "눈", 75: "많은 눈", 77: "싸락눈",
          80: "약한 소나기", 81: "소나기", 82: "강한 소나기", 85: "약한 눈 소나기", 86: "강한 눈 소나기",
          95: "뇌우", 96: "우박을 동반한 뇌우", 99: "우박을 동반한 뇌우"}


def commute_weather(data):
    """Open-Meteo 응답에서 퇴근길(18~19시) 멘트와 우산 필요 여부"""
    h = data["hourly"]
    idx = [i for i, t in enumerate(h["time"]) if int(t[11:13]) in WEATHER_HOURS]
    if not idx:
        raise ValueError("퇴근 시간대 예보 없음")
    temps = [h["temperature_2m"][i] for i in idx]
    feels = [h["apparent_temperature"][i] for i in idx]
    codes = [h["weather_code"][i] for i in idx]
    probs = [h["precipitation_probability"][i] or 0 for i in idx]
    code = max(codes)
    desc = WMO_KO.get(code, "알 수 없음")
    t0, t1 = round(temps[0]), round(temps[-1])
    temp = f"{t0}도" if t0 == t1 else f"{t0}도에서 {t1}도"
    msg = f"오늘 퇴근길 날씨는 {desc}, 기온은 {temp}예요."
    if min(feels) <= min(temps) - 3:
        msg += f"\n바람 때문에 체감은 {round(min(feels))}도라 쌀쌀해요."
    prob = max(probs)
    rain = prob >= 50 or code >= 51
    if rain:
        msg += f"\n비 올 확률 {prob}%, 우산 챙기세요!"
    elif prob >= 20:
        msg += f"\n비 올 확률은 {prob}%예요."
    if min(temps) <= 5:
        msg += "\n따뜻하게 입고 가세요."
    return msg, rain


def raining_now(data):
    """Open-Meteo 현재 날씨에서 지금 비(눈)가 오는 중인지"""
    cur = data["current"]
    return (cur.get("precipitation") or 0) > 0 or (cur.get("weather_code") or 0) >= 51


class RainWatcher(threading.Thread):
    """지금 비가 오는지 한 번 확인해 out 에 (True/False, 오류) 를 넣음"""
    def __init__(self, out):
        super().__init__(daemon=True)
        self.out = out

    def run(self):
        try:
            self.out.put((raining_now(json.loads(fetch_text(RAIN_URL))), None))
        except Exception as e:
            self.out.put((None, e))


class WeatherFetcher(threading.Thread):
    def __init__(self, out, scheduled):
        super().__init__(daemon=True)
        self.out, self.scheduled = out, scheduled

    def run(self):
        try:
            self.out.put((commute_weather(json.loads(fetch_text(WEATHER_URL))), None, self.scheduled))
        except Exception as e:
            self.out.put((None, e, self.scheduled))
