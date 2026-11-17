"""포켓몬 그림·눈입 위치·볼 단계 불러오기"""

import math
import os
import tkinter as tk

from ..species import TARGET_H
from ..sprites import wing_reach
from ..ui import scaled_photo


class CharacterMixin:
    # ---------- 캐릭터 ----------
    def load_character(self):
        """지금 함께하는 포켓몬(self.species)의 그림·눈입 위치·볼 단계를 불러옴"""
        S, sp = self.S, self.species
        img = tk.PhotoImage(file=sp["image"])
        cfg = dict(sp["cfg"])
        h0 = img.height()
        self.char_scale = 1.0  # 원본 그림을 줄인 비율 (밥 먹는 그림도 같은 비율로 줄임)
        if not sp.get("builtin") and h0 > TARGET_H * 1.15:  # 큰 그림은 기준 높이로 줄이고 눈·입 좌표도 같은 비율로
            n = max(1, int(h0 // (TARGET_H * 2)))  # 먼저 정수 배로 거칠게 줄여 속도를 냄
            if n > 1:
                small = tk.PhotoImage()
                small.tk.call(small, "copy", img, "-subsample", n, n)
                img = small
            img = scaled_photo(img, TARGET_H / img.height())
            scale = self.char_scale = TARGET_H / h0
            cfg["eyes"] = [[v * scale for v in e] for e in cfg.get("eyes", [])]
            for key in ("mouth", "beak", "mouth_box"):
                if cfg.get(key):
                    cfg[key] = [v * scale for v in cfg[key]]
        self.img, self.cfg = img, cfg
        self.iw, self.ih = self.img.width(), self.img.height()
        self.has_wings = bool(sp.get("wings"))
        self.has_ball = sp.get("ball", True)  # False 면 몬스터볼(집·볼 단계·볼 안에서 자기) 없이 제자리에서 잠
        # 오른쪽으로 갈 때 쓸 좌우반전 그림 (원본은 왼쪽을 보고 있음)
        self.img_flip = tk.PhotoImage(width=self.iw, height=self.ih)
        self.img_flip.tk.call(self.img_flip, "copy", self.img, "-subsample", -1, 1)
        # 볼로 빨려 들어갈 때 쓰는 점점 작아지는 그림들 (TRAVEL_SCALES 비율): {오른쪽 보는지: [그림들]}
        self.img_travel = {}
        for flip, src in ((False, self.img), (True, self.img_flip)):
            steps = []
            for z, k in self.TRAVEL_SCALES:
                if z == k:
                    steps.append(src)
                    continue
                steps.append(scaled_photo(src, z / k))
            self.img_travel[flip] = steps
        poses = sp["poses"]
        # 자는 모습 그림 (있을 때만). 그림 속 포켓몬은 오른쪽을 보고 있음. 없으면 평소 그림에 눈을 감겨 그림
        self.img_sleep = self.img_sleep_flip = None
        sleep_path = poses["sleep"].get("image")
        if sleep_path and os.path.exists(sleep_path):
            try:
                right = tk.PhotoImage(file=sleep_path)
                left = tk.PhotoImage(width=right.width(), height=right.height())
                left.tk.call(left, "copy", right, "-subsample", -1, 1)
                self.img_sleep_flip, self.img_sleep = right, left  # flip(오른쪽 볼 때) → 원본
            except tk.TclError:
                pass
        # 기분·배고픔에 따른 모습 (그림은 모두 왼쪽을 봄): {이름: (왼쪽 볼 때, 오른쪽 볼 때)}
        #   hungry: 배부름이 HUNGRY_AT 이하,  grumpy: 기분이 GRUMPY_AT 이하
        # 그림 파일이 없으면 pose_overlay 의 눈·입 모양으로 평소 그림 위에 덧그림
        self.pose_imgs, self.pose_overlay = {}, {}
        for name in ("hungry", "grumpy"):
            path = poses[name].get("image")
            if path and os.path.exists(path):
                try:
                    left = tk.PhotoImage(file=path)
                    right = tk.PhotoImage(width=left.width(), height=left.height())
                    right.tk.call(right, "copy", left, "-subsample", -1, 1)
                    self.pose_imgs[name] = (left, right)
                    continue
                except tk.TclError:
                    pass
            if not sp.get("builtin"):
                self.pose_overlay[name] = poses[name]
        if not self.img_sleep:
            self.pose_overlay["sleep"] = poses["sleep"]
        # 이 포켓몬의 볼 단계
        balls = sp["balls"]
        self.BALL_TIERS = tuple((b["level"], b["name"]) for b in balls)
        self.BALL_COLORS = tuple(tuple(b["colors"]) for b in balls)
        self.BALL_STYLES = tuple(b["style"] for b in balls)
        # 날개 펼칠 자리: 날개 끝이 가장 멀리 나가는 자세 + 테두리 두께·곡선 여유 4px (날개 없는 포켓몬은 여유만)
        if self.has_wings:
            self.mx = int(math.ceil(wing_reach() * S * self.ih / 110)) + int(4 * S)
        else:  # 날개가 없으면 우산(비 올 때, 몸 옆에 반지름 = 그림 폭의 절반)이 잘리지 않을 만큼만
            self.mx = max(int(16 * S), int(math.ceil(self.iw * 0.38 + 4 * S)))
        self.mt = int(20 * S)  # zZ 표시할 자리
        if not self.has_wings:  # 우산 꼭대기가 잘리지 않게
            self.mt = max(self.mt, int(math.ceil(self.iw * 0.15 + 9 * S)))
        self.W = self.iw + 2 * self.mx
        self.H = self.mt + self.ih + int(4 * S)
        self.foot = self.mt + self.ih
        self.head = self.mt
        # 밥 먹는 모습(eat)·Claude 작업 중 모습(busy) 그림 (있을 때만, 왼쪽을 봄)
        # img_eat / img_busy = [(왼쪽 볼 때, 오른쪽 볼 때), ...] 프레임 목록. 여러 장이면 ms 마다 넘김
        # 평소 그림과 같은 비율로 줄이고, 창보다 크면 창에 맞춤. 첫 장만 바로 읽고 나머지는 조금씩 (줄이는 데 시간이 걸려서)
        self.img_eat, self.img_busy, self.pose_ms = [], [], {}
        self.load_gen = getattr(self, "load_gen", 0) + 1  # 포켓몬을 바꾸면 읽던 프레임은 버림
        pending = []
        for name in ("eat", "busy"):
            spec = poses.get(name) or {}
            self.pose_ms[name] = spec.get("ms", 120)
            for i, path in enumerate(spec.get("frames", [])):
                if i == 0:
                    self.load_pose_frame(name, path)
                else:
                    pending.append((name, path))
        if pending:
            self.root.after(50, self.load_pose_frames, self.load_gen, pending)

    def load_pose_frame(self, name, path):
        S = self.S
        try:
            left = tk.PhotoImage(file=path)
        except tk.TclError:
            return
        k = min(self.char_scale, self.W / left.width(), (self.H - int(4 * S)) / left.height())
        if k < 0.98:
            left = scaled_photo(left, k)
        right = tk.PhotoImage(width=left.width(), height=left.height())
        right.tk.call(right, "copy", left, "-subsample", -1, 1)
        getattr(self, "img_" + name).append((left, right))

    def load_pose_frames(self, gen, pending):
        """남은 프레임을 한 장씩 읽음 (한꺼번에 읽으면 그동안 화면이 멈춤)"""
        if gen != self.load_gen or not pending:
            return
        self.load_pose_frame(*pending[0])
        if len(pending) > 1:
            self.root.after(30, self.load_pose_frames, gen, pending[1:])
