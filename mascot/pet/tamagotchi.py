"""배부름·기분·친밀도 수치와 저장"""

import json
import random
import time

from ..constants import FULL_DECAY, MOOD_DECAY, SAVE_JSON, UNIT
from ..species import ROWLET_ID
from ..sprites import Item


class TamagotchiMixin:
    # ---------- 다마고치 ----------
    def load_pet(self):
        self.full, self.mood, self.affection = 80.0, 80.0, 0.0
        self.brief_seen = None  # 마지막으로 연 오전 브리핑 메일 UID (다시 켜도 또 알리지 않게)
        self.brief_auto_saved = True  # 오전 브리핑이 오면 클릭 없이 바로 열기
        self.brief_app_saved = True   # 브리핑을 전용 창(Chrome 앱 모드)으로 열기
        self.shutdown_saved = True    # 18:30 이후 자리를 비우면 PC 자동 종료
        self.greet_day = None         # 출근 인사를 한 날짜 (하루 한 번)
        self.last_brief_url = None    # 마지막으로 받은 브리핑 링크 ('다시 열기'용)
        self.weather_said = None      # 퇴근길 날씨를 말한 날짜 (하루 한 번만)
        try:
            with open(SAVE_JSON, encoding="utf-8") as fp:
                d = json.load(fp)
            # 꺼 둔 동안 지난 시간 중 평일만 계산 (휴일은 그대로)
            away = self.workday_seconds(d["t"], time.time()) / UNIT
            # 꺼 둔 동안에도 줄어들지만, 너무 비참해지지 않게 15에서 멈춤
            # 포켓몬마다 따로 저장: pets[id] = {full, mood, affection}. 예전 저장 파일(한 마리)은 나몰빼미 기록으로 이어받음
            pets = d.get("pets")
            if not isinstance(pets, dict):
                pets = {ROWLET_ID: {"full": d["full"], "mood": d["mood"], "affection": d.get("affection", 0.0)}}
            self.pets = pets
            cur = pets.get(self.species_id) or {"full": 80.0, "mood": 80.0, "affection": 0.0}
            self.full = max(min(cur["full"], 15), cur["full"] - away * FULL_DECAY)
            self.mood = max(min(cur["mood"], 15), cur["mood"] - away * MOOD_DECAY)
            self.affection = cur.get("affection", 0.0)
            self.brief_seen = d.get("brief_seen")
            self.brief_auto_saved = d.get("brief_auto", True)
            self.brief_app_saved = d.get("brief_in_app", True)
            self.shutdown_saved = d.get("auto_shutdown", True)
            self.last_brief_url = d.get("last_brief_url")
            self.weather_said = d.get("weather_said")
            self.pomo_day, self.pomo_count = d.get("pomo_day"), d.get("pomo_count", 0)
            self.greet_day = d.get("greet_day")
        except (OSError, ValueError, KeyError):
            pass

    def save_pet(self):
        try:
            self.pets[self.species_id] = {"full": self.full, "mood": self.mood, "affection": self.affection}
            with open(SAVE_JSON, "w", encoding="utf-8") as fp:
                json.dump({"species": self.species_id, "pets": self.pets,
                           "full": self.full, "mood": self.mood, "affection": self.affection,
                           "brief_seen": self.brief_seen, "brief_auto": self.brief_auto_var.get(),
                           "brief_in_app": self.brief_app_var.get(), "last_brief_url": self.last_brief_url,
                           "auto_shutdown": self.shutdown_var.get(),
                           "weather_said": self.weather_said,
                           "pomo_day": self.pomo_day, "pomo_count": self.pomo_count,
                           "greet_day": self.greet_day,
                           "t": time.time()}, fp)
        except OSError:
            pass

    def level(self):
        return 1 + int(self.affection // 10)

    def gain(self, full=0.0, mood=0.0, affection=0.0):
        before = self.level()
        self.full = max(0.0, min(100.0, self.full + full))
        self.mood = max(0.0, min(100.0, self.mood + mood))
        self.affection += affection
        if mood > 0 or affection > 0:
            self.heart_until = time.time() + 1.2
        if self.level() > before:
            old_t, new_t = self.ball_tier(before), self.ball_tier()
            if new_t != old_t:  # 볼 단계가 오름: 빛줄기와 함께 새 볼로
                self.say(f"친밀도가 Lv.{self.level()}이 됐어요!\n"
                         f"{self.BALL_TIERS[old_t][1]}이 {self.BALL_TIERS[new_t][1]}로 바뀌었어요!", 8)
                if self.ball_fx is None:
                    self.ball_fx = {"kind": "flash", "t0": time.time()}
                self.ball_sig = None
            else:
                self.say(f"친밀도가 Lv.{self.level()}이 됐어요!", 4)
            return True
        return False

    def feed(self):
        if self.items:
            self.say("아직 열매가 남아 있어요!", 2)
        elif self.full >= 95:
            self.say("배불러요! 나중에 먹을래요.", 3)
        else:
            S = self.S
            if self.roam_var.get():
                x = self.x + self.W / 2 + random.choice((-1, 1)) * random.uniform(80, 200) * S
                x = min(max(x, self.left), self.right - 20 * S)
                self.items.append(Item(self, x, self.top))
            else:  # 볼 오른쪽에 밥그릇이 나타나고, 그 위에 열매가 떨어짐
                self.show_bowl()
                size = int(20 * S)
                self.items.append(Item(self, self.bowl_cx - size / 2, self.home_area[1], rest_y=self.bowl_rest))

    PET_SEC = 3.0  # 놀아주기(쓰다듬기) 시간

    def play(self):
        """놀아주기: 손이 나타나 머리를 쓰다듬어 줌. 끝까지 쓰다듬으면 기분·친밀도가 오름"""
        if self.state in ("fly", "glide", "flutter", "hover", "fall", "drag"):
            self.say("날고 있어서 쓰다듬을 수 없어요.\n내려앉으면 다시 해 주세요!", 3)
            return
        if self.state == "focus":
            self.say("쿨쿨... (자는 중이에요. 깨운 다음에 쓰다듬어 주세요)", 3)
            return
        if self.state == "pet":
            return
        self.set_state("pet", self.PET_SEC + 0.5)
        self.say(random.choice(["헤헤, 간지러워요!", "기분 좋아요~♥", "더 쓰다듬어 주세요!"]), 2)
        self.root.after(int(self.PET_SEC * 1000), self.pet_done)

    def pet_done(self):
        if self.state != "pet":  # 쓰다듬는 도중에 집어 들었으면 그만
            return
        self.set_state("happy", 1.2)
        if not self.gain(mood=25, affection=2):
            self.say(random.choice(["기분 최고예요!", "또 쓰다듬어 주세요!", "좋아요, 좋아요!"]), 2)
