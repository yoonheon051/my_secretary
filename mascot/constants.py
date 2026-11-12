"""설정 상수: 타이머·화면 갱신·파일 경로·알림 간격·색·말 모음 (여기 숫자만 고치면 동작이 바뀜)"""

import os


UNIT = 60  # 타이머의 1분 (초)
FOCUS_MIN = 25
BREAK_MIN = 5
WORK_STRETCH_MIN = 90  # 이만큼 쉬지 않고 계속 일하면 스트레칭 알림
BREAK_RESET_MIN = 5    # 마우스·키보드 입력이 이만큼 없으면 쉰 것으로 보고 다시 셈
MORNING_UNTIL = 13     # 이 시각(시) 전에 그날 처음 자리에 앉으면 출근 인사 + 오늘 할 일
CLAUDE_NEW_CHAT = "https://claude.ai/new?q="  # 클로드에게 묻기: 새 대화에 질문을 채워서 엶
# 어디서든 누르는 단축키 (Ctrl+Alt+글자): 할 일 빠른 추가, 클로드에게 묻기
HOTKEYS = {1: ("N", "quick_todo"), 2: ("K", "ask_claude"), 3: ("H", "toggle_hidden"),
           4: ("D", "daily_report")}
TICK_MS = 33        # 날거나 떨어질 때 화면 갱신 간격 (약 30번/초). 속도 값들은 이 간격 기준
WALK_TICK_MS = 50   # 걸을 때 (약 20번/초, 한 번에 그만큼 더 걸어서 속도는 같음)
CALM_TICK_MS = 150  # 가만히 서 있거나 잘 때 (CPU 절약)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 프로젝트 폴더 (mascot 폴더의 한 칸 위)


def resource(name):
    return os.path.join(HERE, name)


def _load_local():
    """개인 설정 settings_local.py (GitHub 에 안 올라감). 없으면 settings_local.example.py 의 빈 기본값"""
    import importlib.util
    for name in ("settings_local.py", "settings_local.example.py"):
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("settings_local", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


_LOCAL = _load_local()


def local_setting(key, default=""):
    return getattr(_LOCAL, key, default)


CHAR_PNG = resource("character.png")
CHAR_JSON = resource("character.json")
SAVE_JSON = os.path.join(HERE, "save.json")

# 다마고치 수치 (0~100). 1분마다 줄어드는 양: 배부름은 약 10시간, 기분은 약 8시간이면 바닥
FULL_DECAY = 100 / 600
MOOD_DECAY = 100 / 480
WHINE_MIN = 10  # 배고프거나 심심할 때 조르는 간격(분)
HUNGRY_AT = 30  # 배부름이 이 값 이하면 배고픈 모습(character_hungry.png)으로 보임
GRUMPY_AT = 30  # 기분이 이 값 이하면 뾰로통한 모습(character_grumpy.png)으로 보임 (둘 다면 배고픈 모습이 먼저)
# 모습별 그림 속 부리 위치(그림 크기에 대한 비율, 왼쪽을 볼 때)와 발을 따로 그려야 하는지
POSE_INFO = {"hungry": {"beak": (0.47, 0.55), "feet": True},
             "grumpy": {"beak": (0.33, 0.48), "feet": False}}


HOME_RANGE = 120  # 놀러 간 곳(옮겨 놓은 곳, 열매를 먹은 곳)에서 좌우로 돌아다니는 거리(px)
VISIT_MOVED = (20, 40)  # 옮겨 놓았을 때 그 주변에 머무는 시간(초)
VISIT_PLAYED = (10, 20)  # 바닥에 떨어진 열매를 먹은 뒤 그 주변에 머무는 시간(초)
VISIT_OTHER = (60, 150)  # 다른 모니터로 놀러 갔을 때 머무는 시간(초)
WANDER_CHANCE = 0.02     # 집에서 다음 행동을 고를 때 다른 모니터로 놀러 갈 확률 (몇 분에 한 번쯤)

# 휴일에는 배부름·기분이 줄지 않음 (주말 + Google 공휴일 캘린더 + 내 휴가 일정)
HOLIDAY_ICS = ("https://calendar.google.com/calendar/ical/"
               "ko.south_korea%23holiday%40group.v.calendar.google.com/public/basic.ics")
HOLIDAY_CACHE = os.path.join(HERE, "holidays.json")  # 인터넷이 안 될 때를 위해 받아 둔 휴일 목록
HOLIDAY_REFRESH_SEC = 6 * 3600
VACATION_MARK = "NAMOL-연차:"  # 오전 브리핑 알림 메일 본문에서 내 연차 날짜가 적힌 줄의 시작

# 퇴근길 날씨 (Open-Meteo, 키 필요 없음): 평일 오후 6시에 6~7시 예보를 알려 줌
WEATHER_PLACE = local_setting("WEATHER_PLACE", "서울")  # 위치는 settings_local.py 에서
WEATHER_LAT = local_setting("WEATHER_LAT", 37.5665)
WEATHER_LON = local_setting("WEATHER_LON", 126.9780)
WEATHER_URL = (f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
               "&hourly=temperature_2m,apparent_temperature,weather_code,precipitation_probability"
               "&timezone=Asia%2FSeoul&forecast_days=1")
WEATHER_HOURS = (18, 19)  # 퇴근길로 볼 시간대 (18시 예보, 19시 예보)
WEATHER_SAY_HOUR = 18     # 이 시각(시)에 말함. 그 시간대 안에 PC가 켜지면 그때 말함
UMBRELLA_MIN = 30         # 비 예보면 우산을 들고 있는 시간(분)
RAIN_URL = (f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
            "&current=precipitation,weather_code&timezone=Asia%2FSeoul")
RAIN_CHECK_MIN = 10       # 지금 비가 오는지 확인하는 간격(분). 비가 오는 동안엔 계속 우산을 듬

# 매일 이 시간 동안 신나는 포즈를 하면서 말풍선을 띄움 (시작, 끝(포함 안 함), 말)
DAILY_CHEERS = [("12:25", "12:35", "점심시간이다!"),
                ("18:25", "18:35", "퇴근시간이다!")]

# Google Calendar API (OAuth): client_secret.json 을 폴더에 두고 우클릭 → 'Google 캘린더 연결'
GCAL_CLIENT = os.path.join(HERE, "client_secret.json")  # Google Cloud Console 에서 받은 '데스크톱 앱' 클라이언트
GCAL_TOKEN = os.path.join(HERE, "calendar_token.dat")   # 로그인 후 받은 토큰 (Windows DPAPI 로 암호화)
GCAL_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GCAL_EVENTS = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
GCAL_SYNC_SEC = 6 * 3600  # 연차 일정을 다시 읽어 오는 간격

# Notion API (OAuth 공개 통합): 우클릭 → 'Notion 연결'에서 클라이언트 ID·시크릿을 넣고 브라우저에서 허용
NOTION_CLIENT = os.path.join(HERE, "notion_client.dat")  # 클라이언트 ID·시크릿 (DPAPI 암호화)
NOTION_TOKEN = os.path.join(HERE, "notion_token.dat")    # 허용 후 받은 토큰 (DPAPI 암호화)
NOTION_PORT = 8742
NOTION_REDIRECT = f"http://localhost:{NOTION_PORT}/notion"  # 통합 설정의 '리디렉션 URI'에 이 값 그대로
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
# 아래 네 값은 개인 설정이라 settings_local.py 에 둠 (settings_local.example.py 참고)
NOTION_EMAIL = local_setting("NOTION_EMAIL")      # 이 메일의 Notion 사용자를 '나'로 봄
NOTION_TODO_DB = local_setting("NOTION_TODO_DB")  # TODO 데이터베이스 ID
NOTION_CAL_DB = local_setting("NOTION_CAL_DB")    # 일정 / 일일업무 데이터베이스 ID
NOTION_PAGE_NAME = local_setting("NOTION_PAGE_NAME", "일정·할 일 데이터베이스가 있는 페이지")
NOTION_TODO_CATEGORIES = ["시설/장비", "구매", "네트워크", "행정", "기타"]
REPORT_CHECK_HOUR = 18  # 이 시각(시)에 오늘 일일보고가 Done 인지 확인 (팀 공지: 18:30 까지 기록 + Status 변경)

# 퇴근 후 자동 종료: 이 시각 이후 마우스·키보드 입력이 SHUTDOWN_IDLE_MIN 분 동안 없으면 예고 후 PC 종료.
# 예고 중 아무거나 건드리면 취소. Claude 작업 중에는 끝날 때까지 기다림
SHUTDOWN_AFTER = "18:30"
REPORT_CLOSE_AT = (18, 30)  # 이 시각(시, 분)에 일일 업무 '마감 (Done)' 을 자동으로 누름
SHUTDOWN_IDLE_MIN = 10    # 입력이 이만큼 없으면 자리를 비운 것으로 봄
SHUTDOWN_WARN_SEC = 180   # 예고 후 실제로 끄기까지

# Claude Code 연동: ~/.claude/settings.json 의 훅이 claude_hook.py 로 이 파일에 작업 상태를 적음
# (OneDrive 동기화가 파일을 잡지 않게 %LOCALAPPDATA%\secretary 에 둠. claude_hook.py 와 같은 경로)
CLAUDE_STATUS = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                             "secretary", "claude_status.json")
CLAUDE_CHECK_SEC = 0.5
CLAUDE_STALE_SEC = 6 * 3600  # 이보다 오래 소식 없는 '작업 중' 세션은 무시

MAIL_CFG = os.path.join(HERE, "mail.dat")  # Gmail 주소 + 앱 비밀번호 (Windows DPAPI 로 암호화)
MAIL_POLL_SEC = 60
GMAIL_URL = "https://mail.google.com/mail/u/0/#inbox"
APP_PASSWORD_URL = "https://myaccount.google.com/apppasswords"

KEY = "#ff00fe"  # 이 색은 투명하게 처리됨
# character.json 에 색이 없을 때 쓰는 기본색
BROWN = "#c0915f"
CREAM = "#f7f1e3"
EYE = "#2a1f17"
LEAF = "#58b84f"
FOOT = "#e98a33"
FOOT_D = "#b5641f"

LINES = [
    "오늘도 화이팅이에요.",
    "물 한 잔 마시고 올까요?",
    "잠깐 먼 곳을 보면서 눈 좀 쉬어요.",
    "나뭇잎 나비넥타이, 멋지죠?",
    "고개를 거의 한 바퀴 돌릴 수 있어요.",
    "어깨 힘 빼요. 후~",
]


# ---------- Slack 알림 ----------
SLACK_TOKEN = os.path.join(HERE, "slack_token.dat")  # 사용자 토큰 xoxp-... (DPAPI 암호화)
SLACK_MANIFEST = os.path.join(HERE, "slack_manifest.yaml")  # Slack 앱 만들 때 붙여넣는 설정 (읽기 권한만)
SLACK_POLL_SEC = 60
SLACK_DM_ACTIVE_DAYS = 14   # 이 기간 안에 대화가 있었던 DM 방만 매번 확인 (API 호출을 줄이려고)
SLACK_DM_REFRESH_SEC = 1800  # DM 방 목록을 다시 읽는 간격
