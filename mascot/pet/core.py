"""Rowlet 본체: 창과 수치를 만들고 (__init__), 기능별 믹스인(같은 폴더의 다른 파일들)을 합침"""

import ctypes
import queue
import random
import time
import tkinter as tk
from ctypes import wintypes

from ..constants import KEY, SLACK_TOKEN
from ..google_calendar import GoogleCalendar
from ..notion import NotionClient
from ..secrets_store import load_mail_cfg, load_secret
from ..single_instance import WAKE_EVENT
from ..species import peek_species_id, species_defs
from ..winapi import HotkeyListener
from .character import CharacterMixin
from .tamagotchi import TamagotchiMixin
from .status_card import StatusCardMixin
from .agenda import AgendaMixin
from .notion_ui import NotionUiMixin
from .notifications import NotificationsMixin
from .routines import RoutinesMixin
from .claude_link import ClaudeLinkMixin
from .auto_shutdown import AutoShutdownMixin
from .screen import ScreenMixin
from .ball_home import BallHomeMixin
from .roaming import RoamingMixin
from .main_loop import MainLoopMixin
from .pomodoro import PomodoroMixin
from .quick_actions import QuickActionsMixin
from .collection import CollectionMixin
from .daily_report import DailyReportMixin
from .input_events import InputEventsMixin
from .bubble import BubbleMixin
from .drawing import DrawingMixin


class Rowlet(
        CharacterMixin,
        TamagotchiMixin,
        StatusCardMixin,
        AgendaMixin,
        NotionUiMixin,
        NotificationsMixin,
        RoutinesMixin,
        ClaudeLinkMixin,
        AutoShutdownMixin,
        ScreenMixin,
        BallHomeMixin,
        RoamingMixin,
        MainLoopMixin,
        PomodoroMixin,
        QuickActionsMixin,
        CollectionMixin,
        DailyReportMixin,
        InputEventsMixin,
        BubbleMixin,
        DrawingMixin):
    def __init__(self):
        root = self.root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", KEY)
        root.configure(bg=KEY)

        self.S = root.winfo_fpixels("1i") / 96
        self.species_defs = species_defs()
        self.species_id = peek_species_id(self.species_defs)
        self.species = self.species_defs[self.species_id]
        self.pets = {}  # 포켓몬마다 따로 저장하는 {id: {full, mood, affection}}
        self.load_character()
        self.canvas = tk.Canvas(root, width=self.W, height=self.H, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()

        self.update_area()
        self.x = random.uniform(self.home_area[0], self.home_area[2] - self.W)  # 주 모니터 위쪽에서 나타남
        self.y = float(self.home_area[1])
        self.vx = self.vy = 0.0
        self.dir = random.choice((-1, 1))
        self.bob = 0.0
        self.win_bob = 0  # bob 을 창 위치로 옮긴 양(px)
        self.frame = 0
        self.blink_until = 0.0
        self.dizzy = False
        self.thrown = False
        self.greeted = False
        self.surface = None  # 서 있는 창 (None 이면 화면 바닥)
        self.surf_left = 0
        self.left_surface = None  # 일부러 뛰어내린 창 (바닥에 닿을 때까지 그 창엔 착지 안 함)
        self.leap_ok = False
        self.platforms = []
        self.fly_plat = None
        self.perch_var = tk.BooleanVar(value=True)
        self.roam_var = tk.BooleanVar(value=False)  # True 면 집 없이 화면 전체를 돌아다님
        self.wander_var = tk.BooleanVar(value=False)  # True 면 집 모드에서도 가끔 다른 모니터로 놀러 감 (기본은 끌어다 놓아야만 감)
        # 잠깐 놀러 간 곳: {"surface": 창/None, "dx": 기준 x, "until": 끝나는 시각}. None 이면 바닥의 둥지 집
        self.visit = None
        self.menu_open = False
        self.hidden = False  # Ctrl+Alt+H 로 화면에서 치워 둔 상태
        self.dialog = None  # 열려 있는 설정 창
        # 둥지: 재우기·퇴근 종료 예고 때 나몰빼미가 들어가 있는 곳
        self.in_ball = False        # 볼 안에 들어가 있는지 (이때는 나몰빼미 창을 숨김)
        self.ball_fx = None         # 볼 연출 {"kind": open/shake/burst, "t0": 시작 시각}
        self.ball_sig = None        # 지난번에 그린 볼 모습 (같으면 다시 안 그림)
        self.ball_hold_until = 0.0  # 이 시각까지는 볼 안에 있음 (종료 명령을 보낸 뒤)
        self.ball_click_until = 0.0  # 자는 중 볼을 한 번 눌렀을 때, 이 안에 또 누르면 깨움
        self.cap_t0 = self.rel_t0 = 0.0
        self.travel = 0.0           # 볼로 빨려 들어가거나 나오는 진행도 0~1
        self.travel_room = False    # 들어가고 나오는 동안 창을 아래로 늘렸는지
        self.ball_front = False     # 볼이 나몰빼미 앞에 오는 순간인지
        self.sink_t = 0.0
        self.sink_now = 0           # 볼 위에 서 있을 때 나몰빼미 창을 올리는 양(px, 음수가 위)
        self.ball_route = None      # 볼을 누른 동작이 가는 곳: "pet"(나몰빼미를 누른 것과 같게) / "ball"
        self.build_home()
        self.dragging = False
        self.set_state("flutter")  # 화면 위에서 나타나 집까지 날아옴

        self.pomo_phase = None  # None / "focus" / "break"
        self.pomo_end = 0.0
        self.pomo_count = 0     # 오늘 재운(집중한) 횟수
        self.pomo_day = None    # pomo_count 를 센 날짜
        self.status_win = None  # 상태 카드
        self.card_mouse = False
        self.card_drawn = 0.0
        self.card_size = self.card_pos = None
        self.today_data = None  # 상태 카드용 오늘 (일정, 할 일)
        self.today_at = 0.0
        self.stretch_var = tk.BooleanVar(value=True)
        self.active_since = None       # 쉬지 않고 계속 입력하기 시작한 시각 (BREAK_RESET_MIN 쉬면 None)
        self.last_activity_check = 0.0
        self.last_morning_check = 0.0
        self.hotkey_q = queue.Queue()  # 단축키가 눌리면 이름이 들어옴
        self.hotkeys = HotkeyListener(self.hotkey_q)
        self.hotkeys.start()

        self.items = []
        self.heart_until = 0.0
        self.holiday_q = queue.Queue()
        self.off_days = set()  # 쉬는 날 {'YYYY-MM-DD'} (공휴일 + 내 휴가)
        self.load_holiday_cache()
        self.load_pet()  # 꺼 둔 동안 줄어드는 양을 계산할 때 휴일 목록이 필요해서 그다음에
        self.brief_auto_var = tk.BooleanVar(value=self.brief_auto_saved)
        self.brief_app_var = tk.BooleanVar(value=self.brief_app_saved)  # 브리핑을 전용 창으로 열기
        self.shutdown_var = tk.BooleanVar(value=self.shutdown_saved)    # 18:30 이후 자동 종료
        self.shutdown_at = None        # 종료 예고 중이면 실제로 끌 시각
        self.shutdown_warned = 0.0     # 종료 예고를 시작한 시각 (그 뒤 입력이 있으면 취소)
        self.shutdown_done = None      # 종료 명령을 보낸 날짜 (그날은 다시 안 함)
        self.last_shutdown_check = 0.0
        self.weather_q = queue.Queue()
        self.weather_busy = False
        self.weather_retry_at = 0.0
        self.rain_q = queue.Queue()  # 지금 비 오는지 확인 결과
        self.rain_busy = False
        self.rain_check_at = 0.0
        self.umbrella_until = 0.0
        self.cheering = None  # 지금 띄우고 있는 점심·퇴근 말
        self.last_sig = None   # 지난번에 그린 모습 (같으면 다시 그리지 않음)
        self.last_pos = None
        self.bubble_pos = None
        self.last_tick = self.last_save = self.last_whine = time.time()
        self.last_frame_t = time.time()
        self.step, self.k = 1, 1.0  # 이번 틱에 넘어간 프레임 수, 걷는 거리 배율
        self.last_area_check = self.last_restack = self.last_platforms = 0.0
        self.claude_busy = False       # Claude Code 세션 중 하나라도 작업 중이면 고민하는 모습
        self.claude_mtime = None       # claude_status.json 을 마지막으로 읽었을 때의 수정 시각
        self.claude_seen_t = time.time()  # 이 시각 이후의 이벤트만 알림 (켜기 전 일은 조용히)
        self.last_claude_check = 0.0
        self.claude_notice_until = 0.0  # Claude 알림 말풍선이 떠 있는 동안 (누르면 Claude 창)
        self.last_holiday_fetch = 0.0
        self.was_day_off = None
        self.gcal = GoogleCalendar()
        self.notion = NotionClient()
        self.gcal_q = queue.Queue()  # 캘린더·Notion 작업 결과
        self.vac_sources = {}       # 휴가 날짜 출처별 {google / notion / mail: {날짜}}
        self.last_notion_sync = 0.0
        self.report_checked = None  # 일일보고를 확인한 날짜
        self.report_closed = None   # 18:30 자동 마감을 시도한 날짜
        self.report_url = None      # 클릭하면 열 일일보고 페이지
        self.todo_win = None
        self.rep_win = None  # 일일 업무 창
        self.dex_win = None  # 포켓몬 도감 창
        self.todo_items = []
        self.last_gcal_sync = 0.0
        self.sync_announce = False
        self.sched_win = None   # '내 일정' 창
        self.sched_events = []
        self.agenda_date = None  # 오늘 일정을 보여 준 날짜 (그날 첫 클릭에만 자동으로)

        self.build_bubble()

        self.mail_q = queue.Queue()
        self.mail = None             # MailChecker
        self.mail_known = None       # 지난번에 본 안 읽은 메일 UID 집합 (None 이면 아직 첫 확인 전)
        self.mail_recent = []        # [(보낸 사람, 제목)]
        self.has_letter = False      # 편지봉투를 물고 있는지
        self.brief = None            # 아직 안 연 오전 브리핑 (메일 UID, 링크). 있으면 신문을 물고 있음
        self.brief_since = 0.0
        self.letter_click_until = 0.0
        cfg = load_mail_cfg()
        if cfg:
            self.start_mail(*cfg)

        self.slack_q = queue.Queue()
        self.slack = None              # SlackChecker
        self.slack_err = None          # 마지막으로 알린 Slack 오류 (같은 오류는 다시 안 알림)
        self.slack_notice_until = 0.0  # Slack 알림 말풍선이 떠 있는 동안 (누르면 Slack 열기)
        self.slack_open_to = None      # 누르면 열 대화방 (채널 ID)
        self.slack_announce = False    # 설정 창에서 막 연결했으면 '연결 완료' 를 말함
        tok = load_secret(SLACK_TOKEN)
        if tok and tok.get("token"):
            self.start_slack(tok["token"])

        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_motion)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", self.on_menu)

        # 누가 나몰빼미를 또 켜려고 하면 받는 신호 (already_running). 자동으로 다시 꺼지는 이벤트
        k32 = ctypes.windll.kernel32
        k32.CreateEventW.restype = wintypes.HANDLE
        self.wake_event = k32.CreateEventW(None, False, False, WAKE_EVENT)
        self.tick()
        self.root.after(4000, self.check_hotkeys)
        self.root.after(1000, self.check_wake)

    def check_wake(self):
        """누가 또 켜려고 했으면 '이미 켜져 있어요' 하고 인사"""
        if self.wake_event and ctypes.windll.kernel32.WaitForSingleObject(self.wake_event, 0) == 0:
            self.say("저 여기 있어요!\n(이미 켜져 있어요)", 5)
            if self.state in ("idle", "walk", "sleep", "home", "land"):
                self.set_state("happy", 1.5)
        self.root.after(1000, self.check_wake)

    def check_hotkeys(self):
        """다른 프로그램이 이미 쓰는 단축키라 등록하지 못했으면 알려 줌"""
        if self.hotkeys.failed:
            self.say(f"단축키 {', '.join(self.hotkeys.failed)} 는\n다른 프로그램이 쓰고 있어서 못 썼어요.\n"
                     "상태 카드 메뉴에서 써 주세요.", 8)
