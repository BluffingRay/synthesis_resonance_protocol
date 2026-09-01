import json
import os
import math

W, H = 1280, 720
HEADLESS = False
FPS = 60
PLAYER_ACCEL = 900.0
PLAYER_FRICTION = 0.90
PLAYER_MAX_SPEED = 520.0
PLAYER_RADIUS = 14
FIRE_COOLDOWN = 0.16
VIRTUAL_TARGET_LEN = 400.0
SHARD_LIFE = 9.0
COMBO_WINDOW = 2.5
LIVES_START = 3
SHIELD_RECHARGE = 22.0
HIT_INVULN = 0.6
MAX_HEAT = 45

KILL_XP = {"chaser": 4, "liner": 8, "drifter": 12}
KILL_XP_DEFAULT = 6
BOSS_XP = 2500
XP_WORLD_MULT = [1.4, 1.2, 1.2, 3.0, 4.0, 1.5]

GLOW_MAX_RADIUS = 120

CYAN = (120, 240, 255)
MAGENTA = (255, 90, 220)
RED = (255, 70, 70)
GREEN = (120, 255, 140)
ORANGE = (255, 180, 70)
YELLOW = (255, 240, 110)
WHITE = (235, 245, 255)
TEAL = (110, 240, 200)
GOLD = (255, 205, 110)

SR = 44100
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")

WORLDS = [
    {"id": 0, "name": "NEON CITY", "waves": 12, "arena": (1280, 720), "gimmick": "none",
     "bg": (5, 6, 16), "grid": (35, 80, 110), "star": [(160, 180, 255), (220, 230, 255), (255, 240, 220)],
     "enemy": [(255, 90, 220), (255, 180, 70), (180, 120, 255), (120, 255, 140)],
     "wave": (120, 240, 255), "accent": CYAN, "weights": (3, 2, 2)},
    {"id": 1, "name": "CHROME DESERT", "waves": 14, "arena": (1440, 810), "gimmick": "sandstorm",
     "bg": (16, 8, 4), "grid": (120, 90, 40), "star": [(255, 220, 160), (255, 200, 120), (240, 180, 90)],
     "enemy": [(255, 150, 60), (255, 210, 90), (200, 120, 40), (255, 90, 70)],
     "wave": (255, 200, 100), "accent": ORANGE, "weights": (4, 2, 1)},
    {"id": 2, "name": "VIOLET STORM", "waves": 16, "arena": (1600, 900), "gimmick": "storm",
     "bg": (10, 6, 18), "grid": (90, 70, 140), "star": [(200, 170, 255), (230, 200, 255), (180, 140, 255)],
     "enemy": [(190, 120, 255), (255, 120, 200), (140, 100, 255), (120, 240, 255)],
     "wave": (200, 160, 255), "accent": MAGENTA, "weights": (2, 2, 3)},
    {"id": 3, "name": "AZURE ABYSS", "waves": 18, "arena": (1920, 1080), "gimmick": "mines",
     "bg": (2, 10, 14), "grid": (25, 90, 105), "star": [(160, 220, 255), (120, 210, 230), (200, 255, 240)],
     "enemy": [(90, 220, 200), (150, 255, 170), (60, 180, 220), (200, 255, 220)],
     "wave": (120, 240, 210), "accent": TEAL, "weights": (4, 2, 3)},
    {"id": 4, "name": "OBSIDIAN SIGNAL", "waves": 20, "arena": (2080, 1170), "gimmick": "pulse",
     "bg": (8, 8, 10), "grid": (90, 85, 70), "star": [(255, 240, 210), (230, 220, 190), (255, 210, 160)],
     "enemy": [(230, 220, 180), (255, 200, 120), (200, 190, 160), (255, 230, 190)],
     "wave": (255, 220, 150), "accent": GOLD, "weights": (3, 3, 4)},
    {"id": 5, "name": "CRIMSON PROTOCOL", "waves": 0, "arena": (1760, 990), "gimmick": "overdrive",
     "bg": (14, 4, 8), "grid": (130, 50, 60), "star": [(255, 180, 180), (255, 150, 150), (240, 120, 140)],
     "enemy": [(255, 80, 80), (255, 150, 90), (255, 70, 140), (255, 200, 80)],
     "wave": (255, 140, 140), "accent": RED, "weights": (4, 3, 2)},
]

BOSS_HP = {0: 90, 1: 150, 2: 240, 3: 350, 4: 480}
WIND_STRENGTH = 260.0
WIND_CYCLE = 14.0
WIND_DURATION = 5.0
BOLT_INTERVAL = 2.2
BOLT_RADIUS = 130.0
ITEM_INTERVAL = 11.0
MINE_INTERVAL = 9.0
MINE_LIFE = 6.0
MINE_COUNT = 2
MINE_RADIUS = 20.0
MINE_BLAST = 90.0
MINE_ENEMY_DMG = 2
PULSE_INTERVAL = 7.0
PULSE_WARN = 0.5
PULSE_SPEED = 220.0
PULSE_MAX_R = 1200.0
PULSE_BAND = 60.0
PULSE_PUSH = 300.0
PULSE_PLAYER_PUSH = 200.0
PULSE_ANCHOR_MIN = 420.0
BOSS_WINDUP = 0.55
BOSS_ATTACK_INTERVAL = 3.6
BOSS_ATTACK = {
    3: {"fan": {"n": 3, "spread": 0.63, "speed": 320.0},
        "ring": {"n": 12, "speed": 260.0, "ring_r": 90.0},
        "summon": {"count": 3}},
    4: {"triple": {"n": 3, "spread": 1.05, "speed": 360.0},
        "rings": {"n": 8, "speed": 300.0, "ring_r": 100.0, "double": True},
        "summon": {"count": 4, "kind": "drifter"}},
}
ITEM_TYPES = [
    {"id": "xp", "name": "CACHE", "weight": 5, "color": (120, 240, 255)},
    {"id": "overdrive", "name": "OVERDRIVE", "weight": 3, "color": (255, 180, 70)},
    {"id": "medkit", "name": "MEDKIT", "weight": 1, "color": (120, 255, 140)},
    {"id": "surge", "name": "CORE SURGE", "weight": 2, "color": (255, 240, 110)},
]


class Meta:
    DEFS = [
        {"id": "core_pspeed", "branch": "CORE", "col": 0, "row": 0, "name": "Resonance Bolt",
         "desc": "proj speed +12%", "max": 4, "base": 20, "pre": [], "tier": 1},
        {"id": "core_frate", "branch": "CORE", "col": 0, "row": 1, "name": "Overclock",
         "desc": "fire rate +10%", "max": 5, "base": 30, "pre": [("core_pspeed", 1)], "tier": 1},
        {"id": "core_dmg", "branch": "CORE", "col": 0, "row": 2, "name": "Harmonic Amp",
         "desc": "damage +20%", "max": 6, "base": 40, "pre": [("core_frate", 1)], "tier": 2},
        {"id": "core_multishot", "branch": "CORE", "col": 0, "row": 3, "name": "Split Core",
         "desc": "+1 projectile", "max": 4, "base": 130, "pre": [("core_dmg", 2)], "tier": 2},
        {"id": "aegis_shield", "branch": "AEGIS", "col": 1, "row": 0, "name": "Energy Shield",
         "desc": "absorbs 1 hit each", "max": 3, "base": 100, "pre": [], "tier": 1},
        {"id": "aegis_lives", "branch": "AEGIS", "col": 1, "row": 1, "name": "Hull Shards",
         "desc": "+1 max life", "max": 3, "base": 150, "pre": [("aegis_shield", 1)], "tier": 2},
        {"id": "field_magnet", "branch": "FIELD", "col": 2, "row": 0, "name": "Attractor",
         "desc": "magnet +25%", "max": 5, "base": 20, "pre": [], "tier": 1},
        {"id": "field_combo", "branch": "FIELD", "col": 2, "row": 1, "name": "Momentum",
         "desc": "combo window +0.35s", "max": 3, "base": 40, "pre": [("field_magnet", 1)], "tier": 1},
        {"id": "field_charge", "branch": "FIELD", "col": 2, "row": 2, "name": "Core Feed",
         "desc": "charge gain +12%", "max": 5, "base": 35, "pre": [("field_combo", 1)], "tier": 2},
        {"id": "field_xp", "branch": "FIELD", "col": 2, "row": 3, "name": "Synthesize",
         "desc": "XP gain +20%", "max": 6, "base": 50, "pre": [("field_charge", 1)], "tier": 2},
        {"id": "velocity", "branch": "VELOCITY", "col": 3, "row": 0, "name": "Thrusters",
         "desc": "move speed +7%", "max": 5, "base": 30, "pre": [], "tier": 1},
        {"id": "velocity_pierce", "branch": "VELOCITY", "col": 3, "row": 1, "name": "Sonic Lance",
         "desc": "+1 pierce each", "max": 2, "base": 45, "pre": [("velocity", 2)], "tier": 2},
        {"id": "velocity_homing", "branch": "VELOCITY", "col": 3, "row": 2, "name": "Seeker Gyro",
         "desc": "shots hunt enemies", "max": 1, "base": 90, "pre": [("velocity_pierce", 1)], "tier": 3},
        {"id": "velocity_hyper", "branch": "VELOCITY", "col": 3, "row": 3, "name": "Hyperdrive",
         "desc": "+1 projectile, move +5% each", "max": 1, "base": 160, "pre": [("velocity_homing", 1), ("velocity", 3)], "tier": 4},
        {"id": "aegis_plating", "branch": "AEGIS", "col": 1, "row": 2, "name": "Bastion Plating",
         "desc": "+1 shield each", "max": 3, "base": 110, "pre": [("aegis_lives", 1)], "tier": 3},
        {"id": "aegis_overdrive", "branch": "AEGIS", "col": 1, "row": 3, "name": "Last Stand",
         "desc": "+1 life, damage +15%", "max": 1, "base": 200, "pre": [("aegis_plating", 2), ("aegis_lives", 2)], "tier": 4},
    ]

    def __init__(self, path=SAVE_PATH):
        self.path = path
        self.resonance = 0
        self.levels = {d["id"]: 0 for d in self.DEFS}
        self.world = 0
        self.worlds = 0
        self.save_enabled = True
        self.load()

    def load(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.resonance = int(data.get("resonance", 0))
            for k, v in data.get("upgrades", {}).items():
                if k in self.levels:
                    self.levels[k] = int(v)
            self.world = int(data.get("world", 0))
            self.worlds = int(data.get("worlds", 0))
        except Exception:
            pass
        self.world = max(0, min(self.world, len(WORLDS) - 1))
        self.worlds = max(0, min(self.worlds, len(WORLDS) - 1))

    def save(self):
        if not self.save_enabled:
            return
        try:
            with open(self.path, "w") as f:
                json.dump({"resonance": self.resonance, "upgrades": self.levels,
                           "world": self.world, "worlds": self.worlds}, f, indent=2)
        except Exception:
            pass

    def cost(self, d):
        return int(d["base"] * (1 + 0.6 * self.levels[d["id"]]))

    def lvl(self, uid):
        return self.levels[uid]

    def heat(self):
        return sum(self.levels.values())

    def prereq_met(self, d):
        for pid, minlvl in d["pre"]:
            if self.levels[pid] < minlvl:
                return False
        return True

    def tier_locked(self, d):
        return d.get("tier", 1) >= 2 and self.worlds < 1

    def afford(self, d):
        return self.resonance >= self.cost(d)


UPG_POOL = [
    {"id": "pierce", "name": "PIERCE", "desc": "shots pass through +1 enemy", "max": 3, "weight": 3},
    {"id": "burst", "name": "BURST", "desc": "+1 spread projectile", "max": 3, "weight": 3},
    {"id": "dmg", "name": "AMPLIFY", "desc": "damage +20%", "max": 12, "weight": 4},
    {"id": "frate", "name": "HASTE", "desc": "fire rate +15%", "max": 12, "weight": 4},
    {"id": "speed", "name": "DRIFT", "desc": "move speed +8%", "max": 12, "weight": 2},
    {"id": "pickup", "name": "MAGNET", "desc": "pickup range +30%", "max": 3, "weight": 2},
    {"id": "homing", "name": "SEEKER", "desc": "shots home to enemies", "max": 1, "weight": 2},
    {"id": "shieldc", "name": "SHIELD SURGE", "desc": "refill shield instantly", "max": 99, "weight": 2},
    {"id": "heal", "name": "REPAIR", "desc": "restore 1 life", "max": 99, "weight": 1},
]
UPG_IDS = [u["id"] for u in UPG_POOL]


def xp_next(level):
    if level <= 8:
        return int(10 * level ** 1.65)
    return int(xp_next(8) * (level / 8.0) ** 2.4)


def wrap(text, width):
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
