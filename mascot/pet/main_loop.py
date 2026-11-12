"""매 틱마다 움직임·물리 갱신"""

import math
import random
import time

from ..constants import CALM_TICK_MS, TICK_MS, VISIT_MOVED, WALK_TICK_MS


class MainLoopMixin:
    # ---------- 메인 루프 ----------
    AIRBORNE = ("fall", "hover", "flutter", "fly", "glide")

    def crossed(self, n):
        """이번 틱에 프레임 번호가 n 의 배수를 지났는지 (틱마다 프레임이 여러 개 넘어갈 수 있어서)"""
        return self.frame // n != (self.frame - self.step) // n

    def calm(self):
        """가만히 서 있거나 자는 중이라 화면을 자주 그릴 필요가 없는지.
        움직이는 중, 열매가 있을 때, 창 위에 있을 때(창을 옮기면 따라가야 함), 상태 카드·말풍선 효과 중엔 아님"""
        return (self.state in ("idle", "sleep", "focus") and not self.items and not self.dragging
                and self.surface is None and self.status_win is None
                and time.time() >= self.heart_until and self.ball_fx is None)

    def toggle_hidden(self):
        """Ctrl+Alt+H: 회의·발표 중에 나몰빼미를 화면에서 잠깐 치웠다가 다시 나오게 함"""
        self.hidden = not self.hidden
        if self.hidden:
            self.hide_bubble()
            self.close_status()
            self.hide_bowl()
            for w in [self.root, self.ball_win] + [it.win for it in self.items]:
                w.withdraw()
        else:
            self.root.deiconify()
            self.ball_win.deiconify()
            for it in self.items:
                it.win.deiconify()
            self.last_pos = None
            self.ball_sig = None
            self.last_frame_t = time.time()
            if self.in_ball:
                self.root.withdraw()
            self.restack()

    def tick(self):
        if self.hidden:  # 숨어 있는 동안은 단축키만 확인
            self.update_hotkeys()
            self.root.after(200, self.tick)
            return
        now = time.time()
        # 지난 틱 이후 흐른 시간만큼 프레임을 넘김 (느린 틱에서도 애니메이션·걷는 속도는 같게)
        k = (now - self.last_frame_t) * 1000 / TICK_MS
        self.k = max(1.0, min(5.0, k))           # 걷는 거리 배율
        self.step = max(1, min(10, round(k)))    # 넘길 프레임 수
        self.last_frame_t = now
        self.frame += self.step
        if now - self.last_area_check >= 2:
            self.last_area_check = now
            before = self.home_area
            self.update_area()
            if self.home_area != before:  # 작업 표시줄·해상도·주 모니터가 바뀌면 볼도 옮김
                self.place_home()
        if now - self.last_restack >= 3:  # 다른 '항상 위' 창에 가려지지 않게 가끔 앞뒤 순서를 다시 맞춤
            self.last_restack = now
            self.restack()
        self.check_timers(now)
        self.update_pet(now)
        self.update_mail()
        self.update_brief()
        self.update_holidays(now)
        self.update_gcal(now)
        self.update_weather(now)
        self.update_cheer(now)
        self.update_claude(now)
        self.update_shutdown(now)
        self.check_morning(now)
        self.update_hotkeys()
        self.update_slack()

        self.pick_monitor()  # 지금 있는 모니터의 바닥·위쪽 (모니터마다 높이가 다를 수 있음)
        self.update_ball(now)
        self.update_bowl(now)
        S, st, ground = self.S, self.state, self.ground()
        # 다른 창 목록은 내려앉을 곳을 찾을 때(공중에 있을 때)만 필요함
        if st in self.AIRBORNE and now - self.last_platforms >= 0.5:
            self.refresh_platforms()
        if st == "drag":
            self.surface = self.left_surface = None
        elif st == "fall":
            prev = self.y + self.foot
            self.vy += 0.9 * S
            self.vx *= 0.99
            self.x += self.vx
            self.y += self.vy
            if self.x < self.left or self.x > self.right - self.W:
                self.x = min(max(self.x, self.left), self.right - self.W)
                self.vx = -self.vx * 0.5
            if self.y < self.top:
                self.y, self.vy = self.top, 0
            plat = self.landing(prev)
            if plat or self.y >= ground:
                if plat:
                    self.y = plat[3] - self.foot
                    self.stand_on(plat[0])
                else:
                    self.y = ground
                    self.surface = self.left_surface = None
                self.dizzy = self.thrown and self.vy > 22 * S
                if self.thrown:  # 옮겨 놓은 곳 주변에서 잠시 놀다가 볼로 돌아감
                    self.start_visit(VISIT_MOVED)
                self.thrown = False
                self.vx = self.vy = 0
                self.set_state("land", 1.5 if self.dizzy else 0.3)
                if self.dizzy:
                    self.gain(mood=-5)
                    self.say("어지러워요...", 1.5)
                elif not self.greeted:
                    self.greeted = True
                    if not self.bubble_until:  # 브리핑·메일 알림 같은 말풍선을 덮지 않게
                        self.say("우클릭하면 상태 카드가 나와요.", 5)
        elif st == "hover":
            # 마우스로 옮겨 놓았을 때: 던진 힘은 점점 줄고, 날개를 파닥이며 천천히 내려앉음
            prev = self.y + self.foot
            self.vx *= 0.93
            # 위·아래로 던진 힘이 내려오는 속도로 바뀜. 높이 있으면 빠르게, 땅에 가까울수록 사뿐히
            fall_speed = max(2.5 * S, min(9 * S, (ground - self.y) / 70))
            self.vy += (fall_speed - self.vy) * 0.1
            if abs(self.vx) > 0.8 * S:
                self.dir = 1 if self.vx > 0 else -1
            self.x += self.vx
            self.y += self.vy + math.sin(self.frame * 0.5) * 0.8 * S
            if self.x < self.left or self.x > self.right - self.W:
                self.x = min(max(self.x, self.left), self.right - self.W)
                self.vx = -self.vx * 0.5
            if self.y < self.top:
                self.y, self.vy = self.top, max(self.vy, 0)
            plat = self.landing(prev)
            if plat or self.y >= ground:
                if plat:
                    self.y = plat[3] - self.foot
                    self.stand_on(plat[0])
                else:
                    self.y = ground
                    self.surface = self.left_surface = None
                self.start_visit(VISIT_MOVED)  # 옮겨 놓은 곳 주변에서 잠시 놀다가 볼로
                self.thrown = False
                self.vx = self.vy = 0
                self.set_state("land", 0.3)
        elif st == "flutter":
            # 날개를 파닥이며 천천히 내려오면서 집 쪽으로 이동.
            # 집까지 남은 가로 거리에 맞춰 내려오는 속도를 조절해서 집 근처에 내려앉음
            prev = self.y + self.foot
            cx = self.x + self.W / 2
            d = self.home_cx() - cx
            if abs(d) > 2 * S:
                self.dir = 1 if d > 0 else -1
            hspeed = max(4 * S, min(12 * S, abs(d) / 60))  # 멀면 빠르게, 가까워질수록 천천히 (약 2~3초 안에 도착)
            self.x += self.dir * min(hspeed, abs(d))
            target_y = self.home_y() - self.foot
            frames_left = max(abs(d) / hspeed, 1)
            self.y += max(1.5 * S, min(6 * S, (target_y - self.y) / frames_left))
            self.y += math.sin(self.frame * 0.5) * 0.8 * S  # 파닥일 때 살짝 출렁임
            plat = self.landing(prev)
            if plat or self.y >= ground:
                if plat:
                    self.y = plat[3] - self.foot
                    self.stand_on(plat[0])
                else:
                    self.y = ground
                    self.surface = self.left_surface = None
                self.set_state("land", 0.3)
                if not self.greeted:
                    self.greeted = True
                    if not self.bubble_until:  # 브리핑·메일 알림 같은 말풍선을 덮지 않게
                        self.say("우클릭하면 상태 카드가 나와요.", 5)
        elif st == "fly":
            far = False
            if self.fly_plat:  # 내려앉을 곳 쪽으로
                d = self.fly_plat[0] - (self.x + self.W / 2)
                self.dir = 1 if d > 0 else -1
                self.x += self.dir * min(max(3 * S, min(10 * S, abs(d) / 50)), abs(d))  # 멀면 빠르게
                far = abs(d) > 40 * S
            else:
                self.x += self.dir * 1.5 * S
            if self.y > self.fly_target:
                self.y -= 3 * S
            self.turn_at_edges()
            # 목표 높이에 닿았고 내려앉을 곳 근처면 활공 시작 (멀면 그 높이에서 계속 날아감)
            it = self.target_item()
            # 바닥의 열매·공이 보이면 바로 활공해서 내려감. 밥그릇 열매면 끝까지 날아감
            if (self.y <= self.fly_target and not far) or (it is not None and not it.in_bowl):
                self.set_state("glide")
        elif st == "glide":
            prev = self.y + self.foot
            it = self.target_item()
            if it is not None and it.in_bowl:
                it = None  # 밥그릇 열매면 바닥으로 내리꽂지 말고 가려던 곳에 내려앉기
            if it:  # 먹이나 공이 보이면 그쪽으로 빠르게 내려감
                d = (it.x + it.size / 2) - (self.x + self.W / 2)
                self.dir = 1 if d > 0 else -1
                self.y += 4 * S
                self.x += self.dir * min(3 * S, abs(d))
            elif self.fly_plat:
                d = self.fly_plat[0] - (self.x + self.W / 2)
                self.dir = 1 if d > 0 else -1
                # 내려앉을 곳이 많이 아래면 (바닥이 낮은 모니터 등) 더 빨리 내려감: 약 2초 안에
                drop = self.fly_plat[1] - self.foot - self.y
                self.y += max(1.6 * S, min(8 * S, drop / 60))
                self.x += self.dir * min(2.6 * S, abs(d))
            else:
                self.y += 1.1 * S
                self.x += self.dir * 2.6 * S
            self.turn_at_edges()
            plat = None if it else self.landing(prev)
            if plat or self.y >= ground:
                if plat:
                    self.y = plat[3] - self.foot
                    self.stand_on(plat[0])
                else:
                    self.y = ground
                    self.surface = self.left_surface = None
                self.fly_plat = None
                self.set_state("idle", random.uniform(1, 3))
        elif not self.follow_surface(ground):
            pass  # 발밑이 사라져서 떨어지기 시작함
        else:
            if (st in ("idle", "walk", "sleep", "home") and self.pomo_phase != "focus"
                    and self.target_item()):
                if st == "sleep":
                    self.say("앗, 뭐가 떨어졌다!", 1.5)
                st = "goto"
                self.set_state("goto")
            elif (not self.roam_var.get() and st in ("idle", "walk", "sleep")
                  and self.crossed(15) and not self.at_home()):
                # 놀러 간 시간이 끝났으면 하던 걸 멈추고 볼로 돌아감
                self.go_home()
                st = self.state
            if st == "walk":
                step = (1.0 if self.full < 30 else 1.6) * S * self.k
                if not self.roam_var.get() and self.surface == self.home_surface:
                    # 집 범위를 벗어나려 하면 돌아서기
                    hc, cx = self.home_cx(), self.x + self.W / 2
                    if abs(cx + self.dir * step - hc) > self.home_range():
                        self.dir = 1 if hc > cx else -1
                self.avoid_window_edge(step)
                if self.blocked_ahead(step):  # 바닥이 더 높은 모니터 쪽: 벽처럼 돌아섬
                    self.dir = -self.dir
                self.x += self.dir * step
                self.turn_at_edges()
            elif st == "home":
                if self.surface != self.home_surface:
                    self.go_home()
                else:
                    d = self.home_cx() - (self.x + self.W / 2)
                    if abs(d) < self.home_range() * 0.5:
                        self.set_state("idle", random.uniform(2, 5))
                    elif self.far_from_home():  # 걸어가기엔 멀거나 다른 모니터: 날아서 감
                        self.start_fly()
                    else:
                        self.dir = 1 if d > 0 else -1
                        step = min(1.8 * S * self.k, abs(d))
                        if self.blocked_ahead(step):  # 걸어서 못 올라가는 모니터 경계: 날아서 감
                            self.start_fly()
                        else:
                            self.x += self.dir * step
                            self.turn_at_edges()
            elif st == "goto":
                it = self.target_item()
                if it is None:
                    self.choose_next()
                elif it.in_bowl:
                    # 밥그릇 열매: 주 모니터 바닥을 걸어서 밥그릇 왼쪽으로. 다른 곳(다른 모니터·창 위)에 있으면 날아옴
                    eat_x = self.bowl_cx + self.EAT_DX * S
                    if not self.on_home_floor():
                        self.visit = None
                        self.fly_to(eat_x, self.ball_floor)
                    else:
                        d = eat_x - (self.x + self.W / 2)
                        if abs(d) > 1:
                            self.dir = 1 if d > 0 else -1
                            self.x += self.dir * min(2.2 * S * self.k, abs(d))
                        elif it.near_ground():
                            self.dir = 1  # 밥그릇이 오른쪽에 있어서 오른쪽을 보고 먹기
                            self.reach_item(it)
                else:
                    d = (it.x + it.size / 2) - (self.x + self.W / 2)
                    speed = 2.4 * S
                    self.dir = 1 if d > 0 else -1
                    self.x += self.dir * min(speed, abs(d))
                    self.x = min(max(self.x, self.left), self.right - self.W)
                    at_wall = self.x in (self.left, self.right - self.W)
                    close = abs(d) < 10 * S or (at_wall and abs(d) < self.W / 2)
                    if self.surface is not None:
                        # 창 위에서 바로 아래에 있으면 뛰어내림
                        if abs(d) < self.W / 3:
                            self.drop()
                    elif it.near_ground() and close:
                        self.reach_item(it)
            elif st == "idle" and random.random() < 0.006 * self.step:
                self.dir = -self.dir  # 가끔 반대쪽을 둘러봄
            elif st == "toball":
                self.step_toball(now)
            elif st == "capture":
                self.travel = min(1.0, (now - self.cap_t0) / self.CAPTURE_SEC)
                self.set_ball_front(self.travel >= 0.5)
                if self.travel >= 1.0:
                    self.finish_capture(now)
            elif st == "release":
                p = (now - self.rel_t0) / self.RELEASE_SEC
                if p >= 0.2 and self.in_ball:  # 볼이 열린 뒤에 나몰빼미가 튀어나옴
                    self.show_pet()
                self.travel = min(1.0, max(0.0, (p - 0.2) / 0.8))
                self.set_ball_front(self.travel < 0.5)
                if p >= 1.0:
                    self.set_ball_front(False)
                    self.set_travel_room(False)
                    self.ball_fx = {"kind": "close", "t0": now}
                    self.set_state("happy", 1.3)
            if st in ("focus", "toball", "capture", "release"):
                pass  # 볼 관련 상태는 update_ball·위 단계가 끝낼 때 바뀜
            elif self.until and now >= self.until:
                self.choose_next()

        if not self.in_ball and self.draw(now):  # 모습이 바뀌었을 때만 다시 그림 (볼 안에서는 창이 숨겨져 있음)
            self.draw_sparkles()
            self.draw_hearts(now)
            self.draw_hand()
            self.draw_thinking()
        # 통통 튀는 움직임(bob)은 그림을 다시 그리지 않고 창을 위아래로 옮겨서 표현 (CPU 절약)
        pos = (int(self.x), int(self.y) + self.win_bob + self.sink_now)
        if pos != self.last_pos:  # 움직였을 때만 창 위치를 옮김
            self.last_pos = pos
            self.root.geometry(f"+{pos[0]}+{pos[1]}")
        self.place_bubble(now)
        self.update_status(now)
        if self.calm():
            wait = CALM_TICK_MS
        elif self.state in ("walk", "home") and not self.dragging:
            wait = WALK_TICK_MS
        else:
            wait = TICK_MS
        self.root.after(wait, self.tick)
