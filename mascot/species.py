"""포켓몬 정의: 기본 포켓몬 + pokemon 폴더의 pokemon.json 읽기, 볼 단계, 저장된 마지막 포켓몬"""

import json
import os

from .constants import CHAR_JSON, CHAR_PNG, HERE, SAVE_JSON, resource


# ---------- 포켓몬 ----------
# 기본 나몰빼미 + pokemon\<이름>\pokemon.json 이 있는 폴더마다 한 마리. 폴더 이름이 _ 로 시작하면 양식(건너뜀).
# 한 마리마다 친밀도·배부름·기분(save.json 의 pets)과 볼 단계(balls)를 따로 가짐.
SPECIES_DIR = os.path.join(HERE, "pokemon")
ROWLET_ID = "rowlet"
TARGET_H = 110  # 평소 모습 그림의 기준 높이(px). 이보다 훨씬 큰 그림은 이 높이로 줄여서 씀
# 볼 단계: 친밀도 레벨이 level 이상이면 그 볼. style: plain / super / hyper / master (뚜껑 무늬), colors: 뚜껑 색, 무늬 색, 반짝임 색, 가운데 띠 색(없으면 null)
DEFAULT_BALLS = (
    {"level": 1, "name": "몬스터볼", "style": "plain", "colors": ["#e5322d", None, "#ff9a92", None]},
    {"level": 10, "name": "슈퍼볼", "style": "super", "colors": ["#2f6fd8", "#e5322d", "#a9c8ff", None]},
    {"level": 20, "name": "하이퍼볼", "style": "hyper", "colors": ["#2d2d33", "#ffd23f", "#9a9aab", None]},
    {"level": 30, "name": "마스터볼", "style": "master", "colors": ["#8e44c6", "#ff8fdc", "#d9b3f5", None]},
    {"level": 40, "name": "프리미어볼", "style": "plain", "colors": ["#f6f6f6", None, "#dcdcdc", "#d9382f"]},
)
BALL_STYLES = ("plain", "super", "hyper", "master")
# 배고픈·자는·뾰로통한 모습은 평소 그림 위에 눈과 입 모양만 바꿔 그림 (그림 파일을 따로 주면 그 그림을 씀)
#   eyes: open / closed / squint(질끈) / half(반쯤 감김) / happy,  mouth: none / open / frown / flat / smile
DEFAULT_POSES = {"hungry": {"eyes": "squint", "mouth": "open"},
                 "sleep": {"eyes": "closed", "mouth": "none"},
                 "grumpy": {"eyes": "half", "mouth": "frown"}}
EYE_SHAPES = ("open", "closed", "squint", "half", "happy")
MOUTH_SHAPES = ("none", "open", "frown", "flat", "smile")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fp:
            d = json.load(fp)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def parse_balls(raw):
    """pokemon.json 의 balls → 레벨 순 목록. 잘못됐으면 기본 볼"""
    out = []
    for b in raw or []:
        try:
            colors = list(b.get("colors") or [])[:4]
            colors += [None] * (4 - len(colors))
            if not colors[0]:
                continue
            style = b.get("style") if b.get("style") in BALL_STYLES else "plain"
            out.append({"level": int(b["level"]), "name": str(b.get("name") or "볼"), "style": style, "colors": colors})
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    out.sort(key=lambda b: b["level"])
    if out:
        out[0] = dict(out[0], level=1)  # 맨 처음 볼은 처음부터
    return tuple(out) or DEFAULT_BALLS


def species_defs():
    """{id: 정의}. 'ok' 는 평소 모습 그림이 있어서 함께 키울 수 있는지"""
    defs = {ROWLET_ID: {
        "id": ROWLET_ID, "no": 722, "name": "나몰빼미", "en": "Rowlet", "kind": "풀깃 포켓몬", "types": ["풀", "비행"],
        "web": "https://namu.wiki/w/나몰빼미", "builtin": True, "ok": True, "image": CHAR_PNG, "wings": True,
        "desc": "둥글둥글한 올빼미 포켓몬. 낮에는 햇빛을 받으며 힘을 모으고, 밤이 되면 소리 없이 날아다녀요. "
                "조용하지만 정이 많아서 돌봐 줄수록 곁에 오래 머물러요.",
        "cfg": read_json(CHAR_JSON) or {},
        # 나몰빼미는 사진으로 만든 그림을 씀 (다른 포켓몬은 눈·입 모양으로 바꿈)
        "poses": {"hungry": {"image": resource("character_hungry.png")}, "grumpy": {"image": resource("character_grumpy.png")},
                  "sleep": {"image": resource("character_sleep.png")}},
        "balls": DEFAULT_BALLS}}
    try:
        names = sorted(os.listdir(SPECIES_DIR))
    except OSError:
        names = []
    for name in names:
        folder = os.path.join(SPECIES_DIR, name)
        if name[:1] in "_." or not os.path.isdir(folder) or name == ROWLET_ID:
            continue
        d = read_json(os.path.join(folder, "pokemon.json"))
        if d is None:
            continue
        img = os.path.join(folder, d.get("image") or "character.png")
        poses = {}
        for pn, base in DEFAULT_POSES.items():
            spec = dict(base)
            given = (d.get("poses") or {}).get(pn) or {}
            for k in ("eyes", "mouth"):
                if given.get(k) in (EYE_SHAPES if k == "eyes" else MOUTH_SHAPES):
                    spec[k] = given[k]
            if given.get("image") and os.path.isfile(os.path.join(folder, given["image"])):
                spec["image"] = os.path.join(folder, given["image"])
            poses[pn] = spec
        eyes = [list(map(float, e)) for e in (d.get("eyes") or []) if isinstance(e, (list, tuple)) and len(e) == 4]
        mouth = d.get("mouth")
        mouth = list(map(float, mouth)) if isinstance(mouth, (list, tuple)) and len(mouth) == 2 else None
        mbox = d.get("mouth_box")
        mbox = list(map(float, mbox)) if isinstance(mbox, (list, tuple)) and len(mbox) == 4 else None
        defs[name] = {
            "id": name, "no": d.get("no") if isinstance(d.get("no"), int) and d.get("no") > 0 else None,
            "name": str(d.get("name") or name), "en": str(d.get("en") or ""), "kind": str(d.get("kind") or ""),
            "types": [str(t) for t in (d.get("types") or [])], "desc": str(d.get("desc") or ""), "web": d.get("web"),
            "builtin": False, "ok": os.path.isfile(img), "image": img if os.path.isfile(img) else None,
            "wings": bool(d.get("wings", False)), "poses": poses, "balls": parse_balls(d.get("balls")),
            "cfg": {"eyes": eyes, "mouth": mouth, "mouth_box": mbox, "beak": mouth, "face": d.get("face") or "#f8f7f1",
                    "outline": d.get("outline") or "#22201e"}}
    return defs


def peek_species_id(defs):
    """save.json 에 적힌, 마지막으로 함께하던 포켓몬 (없어졌거나 그림이 없으면 나몰빼미)"""
    d = read_json(SAVE_JSON) or {}
    sid = d.get("species")
    return sid if sid in defs and defs[sid]["ok"] else ROWLET_ID
