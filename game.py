"""SYNTHESIS: Resonance Protocol.
Procedural audiovisual survival with a node tech tree (save.json), in-run
leveling (pick 1 of 3), and unlockable worlds. Split across game_defs.py,
game_audio.py, game_entities.py, and this orchestrator module."""
import math
import random
import sys

import numpy as np
import pygame

import game_defs
from game_defs import *
from game_defs import Meta, WORLDS, UPG_POOL, UPG_IDS, xp_next, KILL_XP, KILL_XP_DEFAULT, BOSS_XP, XP_WORLD_MULT
from game_audio import AudioEngine
from game_entities import Starfield, Player, Projectile, Enemy, Shard, Glow, Boss, Item


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("SYNTHESIS: Resonance Protocol")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 26)
        self.smallfont = pygame.font.SysFont("consolas", 18)
        self.bigfont = pygame.font.SysFont("consolas", 64)
        self.audio = AudioEngine()
        self.stars = Starfield()
        self.meta = Meta()
        self.t = 0.0
        self.state = "menu"
        self.menu_sel = 0
        self.shop_sel = 0
        self.world_sel = self.meta.world
        self.record = 0
        self.arena = (W, H)
        self.cam = [0, 0]
        self.reset()

    def world(self):
        return WORLDS[self.meta.world]

    def reset(self):
        aw, ah = self.arena = self.world()["arena"]
        self.player = Player(aw / 2, ah / 2)
        self.run_upgrades = {uid: 0 for uid in UPG_IDS}
        self.recompute_stats()
        self.player.move_mult = self.stats["move"]
        self.player.level = self.level = 1
        self.xp = 0
        self.levelups = 0
        self.levelup_options = []
        self.levelup_sel = 0
        self.enemies = []
        self.shots = []
        self.shards = []
        self.particles = []
        self.items = []
        self.bolts = []
        self.boss = None
        self.win = False
        self.wind_dir = (0.0, 0.0)
        self.wind_t = 0.0
        self.wind_active = 0.0
        self.bolt_t = 0.0
        self.item_t = ITEM_INTERVAL * 0.5
        self.overdrive_t = 0.0
        self.mines = []
        self.mine_t = MINE_INTERVAL * 0.6
        self.pulses = []
        self.pulse_t = 5.0
        self.boss_shots = []
        self.cam = [0, 0]
        self.score = 0
        self.lives = self.max_lives
        self.shield_count = self.stats["shield_max"]
        self.shield_regen = SHIELD_RECHARGE
        self.wave = 0
        self.wave_timer = 2.0
        self.wave_banner = 0.0
        self.banner_text = ""
        self.combo = 0
        self.combo_timer = 0.0
        self.multiplier = 1
        self.hit_i = 0.0
        self.charge = 0.0
        self.shake = 0.0
        self.flash = 0.0
        self.essence_earned = 0
        self.new_unlock = None
        self._res_applied = False
        self.last_mouse = np.array([aw / 2, ah / 2])
        self.last_mouse_t = -999.0

    def recompute_stats(self):
        m = self.meta.levels
        u = self.run_upgrades
        s = {}
        s["cooldown"] = FIRE_COOLDOWN / ((1 + 0.10 * m["core_frate"]) * (1 + 0.15 * u["frate"]))
        s["damage"] = (1 + 0.20 * m["core_dmg"]) * (1 + 0.15 * m["aegis_overdrive"]) * (1 + 0.20 * u["dmg"])
        s["projectiles"] = 1 + m["core_multishot"] + u["burst"] + m["velocity_hyper"]
        s["pspeed"] = 760 * (1 + 0.12 * m["core_pspeed"])
        s["pierce"] = u["pierce"] + m["velocity_pierce"]
        s["homing"] = (u["homing"] > 0) or (m["velocity_homing"] > 0)
        s["move"] = (1 + 0.07 * m["velocity"]) * (1 + 0.05 * m["velocity_hyper"]) * (1 + 0.08 * u["speed"])
        s["magnet"] = 160 * (1 + 0.25 * m["field_magnet"]) * (1 + 0.30 * u["pickup"])
        s["charge_gain"] = 0.03 * (1 + 0.12 * m["field_charge"])
        s["combo_window"] = COMBO_WINDOW + 0.35 * m["field_combo"]
        s["max_lives"] = LIVES_START + m["aegis_lives"] + m["aegis_overdrive"]
        s["shield_max"] = m["aegis_shield"] + m["aegis_plating"]
        s["xp"] = 1 + 0.20 * m["field_xp"]
        s["heat"] = min(MAX_HEAT, self.meta.heat())
        self.stats = s
        self.max_lives = s["max_lives"]

    def multiplier_for(self):
        return 1 << min(self.combo // 4, 3)

    def multiplier_color(self):
        m = self.multiplier
        if m >= 8:
            return RED
        if m >= 4:
            return ORANGE
        if m >= 2:
            return MAGENTA
        return CYAN

    def nearest_enemy(self):
        best, nd = None, 1e18
        p = self.player
        for e in self.enemies:
            d = math.hypot(e.pos[0] - p.pos[0], e.pos[1] - p.pos[1])
            if d < nd:
                nd, best = d, e
        return best

    def _aim_point(self, key_state=None):
        p = self.player
        if self.t - self.last_mouse_t < 0.8:
            return np.array(self.last_mouse, dtype=float) + np.array(self.cam, dtype=float)
        if key_state is None:
            key_state = pygame.key.get_pressed()
        dx = (1 if key_state[pygame.K_RIGHT] else 0) - (1 if key_state[pygame.K_LEFT] else 0)
        dy = (1 if key_state[pygame.K_DOWN] else 0) - (1 if key_state[pygame.K_UP] else 0)
        if dx or dy:
            nd = math.hypot(dx, dy)
            if nd < 1:
                nd = 1
            return p.pos + np.array([dx / nd * VIRTUAL_TARGET_LEN, dy / nd * VIRTUAL_TARGET_LEN])
        n = self.nearest_enemy()
        if n is None and self.boss is not None and not self.boss.dead:
            n = self.boss
        if n is None:
            return None
        return n.pos

    def fire(self):
        p = self.player
        s = self.stats
        od = self.overdrive_t > 0
        p.fire_timer = s["cooldown"] * (0.6 if od else 1.0)
        aim = self._aim_point()
        if aim is None:
            return
        d = aim - p.pos
        nd = math.hypot(d[0], d[1])
        if nd < 1:
            nd = 1
        base = d / nd * s["pspeed"]
        dmg = s["damage"] * (1.5 if od else 1.0)
        n_shots = s["projectiles"]
        for i in range(n_shots):
            if n_shots > 1:
                ang = (i - (n_shots - 1) / 2) * 0.12
                c, sn = math.cos(ang), math.sin(ang)
                v = np.array([base[0] * c - base[1] * sn, base[0] * sn + base[1] * c])
            else:
                v = base
            self.shots.append(Projectile(p.pos, v, damage=dmg,
                                         pierce=s["pierce"], homing=s["homing"],
                                         color=self.world()["wave"]))
        self.audio.shoot()

    def spawn_enemy(self):
        wl = self.world()
        kind = random.choices(["chaser", "liner", "drifter"], weights=wl["weights"])[0]
        aw, ah = self.arena
        edge = random.randrange(4)
        if edge == 0:
            pos = (random.uniform(20, aw - 20), -30)
        elif edge == 1:
            pos = (random.uniform(20, aw - 20), ah + 30)
        elif edge == 2:
            pos = (-30, random.uniform(20, ah - 20))
        else:
            pos = (aw + 30, random.uniform(20, ah - 20))
        scale = 1.0 + self.stats["heat"] * 0.06
        ramp_step = {"overdrive": 0.11, "mines": 0.10, "pulse": 0.12}.get(wl["gimmick"], 0.08)
        ramp = 1.0 + (self.wave - 1) * ramp_step
        kmult = {"chaser": 1.3, "liner": 1.0, "drifter": 0.8}[kind]
        cap = 620 if kind == "chaser" else 500
        speed = random.uniform(120, 190) * min(ramp, 2.0)
        speed += random.uniform(0, 24 * min(self.wave, 12))
        speed = min(speed * min(scale, 1.6) * kmult, cap)
        hp = 1
        if self.wave >= 4:
            hp = 2
        if self.wave >= 9:
            hp = 3
        if self.wave >= 14:
            hp = 4
        hp = int(round(hp * (1 + 0.12 * (self.wave - 1)) * scale))
        color = random.choice(wl["enemy"])
        self.enemies.append(Enemy(kind, pos, speed, hp, color))

    def update(self, dt):
        self.t += dt
        if self.state != "playing":
            self.audio.set_state(0.15, 0)
            return
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.arena)
        p = self.player
        wl = self.world()

        self.update_cam()
        wind = self.update_wind(dt, wl)

        if p.alive and p.can_fire():
            self.fire()

        spd = math.hypot(p.vel[0], p.vel[1])
        if spd > 60:
            self.particles.append({
                "x": p.pos[0], "y": p.pos[1],
                "vx": -p.vel[0] * 0.05, "vy": -p.vel[1] * 0.05,
                "t": 0.4, "color": self.multiplier_color(), "glow": True,
            })

        prev_enemies = len(self.enemies)
        for e in self.enemies:
            e.update(dt, p, self.arena)
            if wind != (0.0, 0.0):
                e.pos += np.array(wind) * 0.6 * dt
        self.enemies = [e for e in self.enemies if not e.dead]

        for s in self.shots:
            s.steer(self.enemies)
            s.update(dt, self.arena)
        self.shots = [s for s in self.shots if not s.dead]

        for s in self.shots:
            for e in self.enemies:
                if s.dead:
                    break
                if math.hypot(s.pos[0] - e.pos[0], s.pos[1] - e.pos[1]) < e.radius + s.radius:
                    e.hp -= s.damage
                    self.burst(s.pos, (180, 240, 255), 5, glow=True)
                    self.shake = min(self.shake + 2, 14)
                    if s.pierce > 0:
                        s.pierce -= 1
                    else:
                        s.dead = True
                    if e.hp <= 0:
                        e.dead = True
                        self.kill_enemy(e)
        self.shots = [s for s in self.shots if not s.dead]
        self.enemies = [e for e in self.enemies if not e.dead]

        for s in self.shots:
            if s.dead:
                continue
            for m in self.mines:
                if m["dead"]:
                    continue
                if math.hypot(s.pos[0] - m["pos"][0], s.pos[1] - m["pos"][1]) < MINE_RADIUS + s.radius:
                    s.dead = True
                    self.detonate_mine(m)
                    break

        if self.boss and not self.boss.dead:
            for pos in self.boss.update(dt, p, self.arena):
                self.spawn_minion(pos, kind=self.boss._spawn_kind)
            for v in self.boss.pending_shots:
                self.boss_shots.append(Projectile(self.boss.pos, v, damage=1.0, color=wl["accent"]))
            self.boss.pending_shots = []
            for s in self.shots:
                if s.dead:
                    continue
                if math.hypot(s.pos[0] - self.boss.pos[0], s.pos[1] - self.boss.pos[1]) < self.boss.radius + s.radius:
                    s.dead = True
                    self.burst(s.pos, (180, 240, 255), 6, glow=True)
                    self.shake = min(self.shake + 4, 20)
                    self.boss.hp -= s.damage
                    if self.boss.hp <= 0:
                        self.kill_boss()
                        break
            if self.boss.dead:
                self.boss = None

        for s in self.boss_shots:
            s.update(dt, self.arena)
        self.boss_shots = [s for s in self.boss_shots if not s.dead]
        if p.alive:
            for s in self.boss_shots:
                if math.hypot(s.pos[0] - p.pos[0], s.pos[1] - p.pos[1]) < s.radius + p.radius:
                    s.dead = True
                    self.damage_player()
                    break

        if prev_enemies > 0 and not self.enemies and not self.boss and self.wave > 0:
            self.wave_timer = 1.2

        if p.alive:
            for e in self.enemies:
                if math.hypot(e.pos[0] - p.pos[0], e.pos[1] - p.pos[1]) < e.radius + p.radius - 2:
                    self.damage_player()
                    break
            if self.boss and not self.boss.dead:
                if math.hypot(self.boss.pos[0] - p.pos[0], self.boss.pos[1] - p.pos[1]) < self.boss.radius + p.radius - 2:
                    self.damage_player()

        for sh in self.shards:
            if wind != (0.0, 0.0):
                sh.pos += np.array(wind) * dt
            if sh.update(dt, p, self.stats["magnet"]):
                self.score += 10
                self.combo += 1
                self.combo_timer = self.stats["combo_window"]
                cg = self.stats["charge_gain"] * (1.4 if wl["gimmick"] == "overdrive" else 1.0)
                self.charge = min(1.0, self.charge + cg)
                self.multiplier = self.multiplier_for()
                self.audio.pickup()
                self.grant_xp(2)
        self.shards = [s for s in self.shards if not s.dead]
        if len(self.shards) > 120:
            self.shards = self.shards[-120:]

        if wl["gimmick"] == "mines":
            self.mine_t -= dt
            if self.mine_t <= 0:
                self.mine_t = MINE_INTERVAL
                for _ in range(MINE_COUNT):
                    self.spawn_mine()
            for m in self.mines:
                m["t"] -= dt
                if m["t"] <= 0:
                    m["dead"] = True
                    self.burst(m["pos"], wl["accent"], 10, glow=True)
            for m in self.mines:
                if m["dead"]:
                    continue
                if math.hypot(self.player.pos[0] - m["pos"][0], self.player.pos[1] - m["pos"][1]) < MINE_RADIUS + self.player.radius:
                    self.detonate_mine(m)
                    continue
                for e in self.enemies:
                    if math.hypot(e.pos[0] - m["pos"][0], e.pos[1] - m["pos"][1]) < MINE_RADIUS + e.radius:
                        self.detonate_mine(m)
                        break
            self.mines = [m for m in self.mines if not m["dead"]]

        self.item_t -= dt
        if self.item_t <= 0:
            self.item_t = ITEM_INTERVAL
            self.spawn_item()
        for it in self.items:
            it.update(dt, wind, p, self.stats["magnet"])
            if math.hypot(it.pos[0] - p.pos[0], it.pos[1] - p.pos[1]) < p.radius + 18:
                self.collect_item(it)
        self.items = [it for it in self.items if not it.dead]

        if wl["gimmick"] == "storm":
            self.bolt_t -= dt
            if self.bolt_t <= 0:
                self.bolt_t = BOLT_INTERVAL
                self.strike()

        if wl["gimmick"] == "pulse":
            self.pulse_t -= dt
            if self.pulse_t <= 0:
                self.pulse_t = PULSE_INTERVAL
                self.spawn_pulse()
            for pu in self.pulses:
                pu["warn"] -= dt
                pu["r"] += PULSE_SPEED * dt
                if pu["r"] > 40.0:
                    self.apply_pulse(pu, dt)
            self.pulses = [pu for pu in self.pulses if pu["r"] < PULSE_MAX_R + PULSE_BAND]

        if self.overdrive_t > 0:
            self.overdrive_t = max(0.0, self.overdrive_t - dt)

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0
                self.multiplier = 1

        if self.charge > 0:
            self.charge = max(0.0, self.charge - 0.012 * dt)

        if self.shield_count < self.stats["shield_max"]:
            self.shield_regen -= dt
            if self.shield_regen <= 0:
                self.shield_regen = SHIELD_RECHARGE
                self.shield_count += 1

        for pt in self.particles:
            pt["x"] += pt["vx"] * dt
            pt["y"] += pt["vy"] * dt
            pt["vx"] *= 0.96
            pt["vy"] *= 0.96
            pt["t"] -= dt
        if len(self.particles) > 700:
            self.particles = self.particles[-700:]
        self.particles = [pt for pt in self.particles if pt["t"] > 0]

        self.shake = max(0.0, self.shake - dt * 30)
        self.flash = max(0.0, self.flash - dt * 2)
        self.wave_banner = max(0.0, self.wave_banner - dt)
        self.hit_i = max(0.0, self.hit_i - dt)

        for b in self.bolts:
            b["t"] -= dt
        self.bolts = [b for b in self.bolts if b["t"] > 0]

        if not self.enemies:
            if self.boss is None:
                if wl["waves"] and self.wave >= wl["waves"]:
                    self.spawn_boss()
                elif self.wave_timer <= 0:
                    self.wave += 1
                    self.start_wave()
                else:
                    self.wave_timer -= dt

        self.audio.set_state(self.charge, self.combo)

        if self.lives <= 0 and not self._res_applied:
            self.end_run(won=False)

    def update_cam(self):
        aw, ah = self.arena
        p = self.player.pos
        self.cam = [max(0.0, min(p[0] - W / 2, aw - W)),
                    max(0.0, min(p[1] - H / 2, ah - H))]

    def update_wind(self, dt, wl):
        wind = (0.0, 0.0)
        if wl["gimmick"] == "sandstorm":
            self.wind_t -= dt
            if self.wind_t <= 0:
                self.wind_t = WIND_CYCLE
                self.wind_active = WIND_DURATION
                self.wind_dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)])
            if self.wind_active > 0:
                self.wind_active -= dt
                wind = (self.wind_dir[0] * WIND_STRENGTH, self.wind_dir[1] * WIND_STRENGTH)
                self.player.vel += np.array(wind) * 0.35 * dt
                if random.random() < 0.5:
                    a = math.atan2(wind[1], wind[0])
                    px, py = self.player.pos
                    self.particles.append({
                        "x": px + random.uniform(-400, 400),
                        "y": py + random.uniform(-300, 300),
                        "vx": math.cos(a) * 320, "vy": math.sin(a) * 320,
                        "t": 0.6, "color": (210, 170, 90), "glow": False,
                    })
        return wind

    def spawn_minion(self, pos, kind="chaser"):
        wl = self.world()
        speed = min(180 + 20 * self.meta.world, 300)
        self.enemies.append(Enemy(kind, pos, speed, 2, random.choice(wl["enemy"])))

    def spawn_mine(self):
        aw, ah = self.arena
        x = np.clip(self.player.pos[0] + random.uniform(-320, 320), 60, aw - 60)
        y = np.clip(self.player.pos[1] + random.uniform(-220, 220), 60, ah - 60)
        self.mines.append({"pos": np.array([x, y]), "t": MINE_LIFE, "dead": False})

    def detonate_mine(self, m):
        if m["dead"]:
            return
        m["dead"] = True
        wl = self.world()
        self.burst(m["pos"], wl["accent"], 18, glow=True)
        self.shake = min(self.shake + 10, 24)
        for e in self.enemies:
            if math.hypot(e.pos[0] - m["pos"][0], e.pos[1] - m["pos"][1]) < MINE_BLAST + e.radius:
                e.hp -= MINE_ENEMY_DMG
                if e.hp <= 0:
                    e.dead = True
                    self.kill_enemy(e)
        if math.hypot(self.player.pos[0] - m["pos"][0], self.player.pos[1] - m["pos"][1]) < MINE_BLAST + self.player.radius:
            self.damage_player()

    def spawn_pulse(self):
        aw, ah = self.arena
        x, y = 0.0, 0.0
        for _ in range(40):
            x = random.uniform(80, aw - 80)
            y = random.uniform(80, ah - 80)
            if math.hypot(x - self.player.pos[0], y - self.player.pos[1]) >= PULSE_ANCHOR_MIN:
                break
        self.pulses.append({"pos": np.array([x, y]), "r": 0.0, "warn": PULSE_WARN})

    def apply_pulse(self, pu, dt):
        a = pu["pos"]
        for e in self.enemies:
            d = e.pos - a
            nd = math.hypot(d[0], d[1])
            if nd > 1 and pu["r"] - PULSE_BAND < nd < pu["r"] + PULSE_BAND:
                e.pos += d / nd * PULSE_PUSH * dt
        for sh in self.shards:
            d = sh.pos - a
            nd = math.hypot(d[0], d[1])
            if nd > 1 and pu["r"] - PULSE_BAND < nd < pu["r"] + PULSE_BAND:
                sh.pos += d / nd * PULSE_PUSH * 0.5 * dt
        for it in self.items:
            d = it.pos - a
            nd = math.hypot(d[0], d[1])
            if nd > 1 and pu["r"] - PULSE_BAND < nd < pu["r"] + PULSE_BAND:
                it.pos += d / nd * PULSE_PUSH * 0.5 * dt
        d = self.player.pos - a
        nd = math.hypot(d[0], d[1])
        if nd > 1 and pu["r"] - PULSE_BAND < nd < pu["r"] + PULSE_BAND:
            self.player.vel += d / nd * PULSE_PLAYER_PUSH * dt

    def spawn_boss(self):
        wl = self.world()
        hp = BOSS_HP.get(self.meta.world, 200)
        hp = int(hp * (1 + 0.15 * self.stats["heat"]))
        aw, ah = self.arena
        p = self.player.pos
        cx = np.clip(p[0] + random.choice([-1, 1]) * min(aw, 720) * 0.5, 70, aw - 70)
        cy = np.clip(p[1] + random.choice([-1, 1]) * min(ah, 420) * 0.5, 70, ah - 70)
        names = {3: "ABYSSAL ANCHOR", 4: "SIGNAL WRAITH"}
        self.boss = Boss([cx, cy], hp, wl["accent"], world_id=self.meta.world, name=names.get(self.meta.world, "PROTOCOL ANCHOR"))
        self.boss.set_bounds(self.arena)
        self.wave_banner = 2.2
        self.banner_text = "PROTOCOL ANCHOR DETECTED"
        self.audio.levelup()

    def kill_boss(self):
        b = self.boss
        self.boss.dead = True
        self.score += 5000
        self.grant_xp(BOSS_XP)
        self.audio.explode()
        self.burst(b.pos, YELLOW, 60, glow=True)
        self.shake = 30
        self.flash = 0.5
        aw, ah = self.arena
        for _ in range(18):
            sp = b.pos + np.random.uniform(-20, 20, 2)
            sp[0] = np.clip(sp[0], 24, aw - 24)
            sp[1] = np.clip(sp[1], 24, ah - 24)
            self.shards.append(Shard(sp))
        self.win = True
        self.end_run(won=True)

    def end_run(self, won):
        self._res_applied = True
        self.state = "over"
        if self.score > self.record:
            self.record = self.score
        wl = self.world()
        base = 8 + self.wave * 3 + self.score // 600
        mult = (2.5 if won else 1.0) * (self.meta.world + 1)
        essence = int(max(12, base * mult))
        if won:
            essence += 50 + 40 * self.meta.world
            nxt = self.meta.world + 1
            if nxt < len(WORLDS) and nxt > self.meta.worlds:
                self.new_unlock = WORLDS[nxt]["name"]
            if nxt < len(WORLDS):
                self.meta.worlds = max(self.meta.worlds, nxt)
        self.essence_earned = essence
        self.meta.resonance += essence
        self.meta.save()
        self.audio.gameover()

    def strike(self):
        aw, ah = self.arena
        if self.enemies:
            target = random.choice(self.enemies).pos
        elif self.boss and not self.boss.dead:
            target = self.boss.pos
        else:
            target = np.array([random.uniform(60, aw - 60), random.uniform(60, ah - 60)])
        self.bolts.append({"pos": np.array(target, dtype=float), "t": 0.25})
        for e in list(self.enemies):
            if math.hypot(e.pos[0] - target[0], e.pos[1] - target[1]) < BOLT_RADIUS:
                e.hp -= 3
                if e.hp <= 0:
                    e.dead = True
                    self.kill_enemy(e)
        if self.boss and not self.boss.dead:
            if math.hypot(self.boss.pos[0] - target[0], self.boss.pos[1] - target[1]) < BOLT_RADIUS:
                self.boss.hp -= 3
                if self.boss.hp <= 0:
                    self.kill_boss()
        if math.hypot(self.player.pos[0] - target[0], self.player.pos[1] - target[1]) < 150:
            self.damage_player()
        self.burst(target, (200, 170, 255), 14, glow=True)

    def spawn_item(self):
        wl = self.world()
        weights = [t["weight"] for t in ITEM_TYPES]
        if wl["gimmick"] == "sandstorm":
            weights[0] += 3
        elif wl["gimmick"] == "storm":
            weights[3] += 3
        elif wl["gimmick"] == "overdrive":
            weights[1] += 2
        elif wl["gimmick"] == "mines":
            weights[0] += 1
            weights[2] += 2
        elif wl["gimmick"] == "pulse":
            weights[1] += 3
            weights[3] += 1
        t = random.choices(ITEM_TYPES, weights=weights)[0]
        aw, ah = self.arena
        x = np.clip(self.player.pos[0] + random.uniform(-320, 320), 40, aw - 40)
        y = np.clip(self.player.pos[1] + random.uniform(-220, 220), 40, ah - 40)
        self.items.append(Item([x, y], t["id"], t))

    def collect_item(self, it):
        it.dead = True
        self.audio.pickup()
        t = it.itype
        if t == "xp":
            self.score += 200
            self.grant_xp(30)
            for _ in range(5):
                self.shards.append(Shard(it.pos))
        elif t == "overdrive":
            self.overdrive_t = 6.0
            self.burst(it.pos, ORANGE, 18, glow=True)
        elif t == "medkit":
            self.lives = min(self.max_lives, self.lives + 1)
            self.burst(it.pos, GREEN, 16, glow=True)
        elif t == "surge":
            self.charge = 1.0
            self.burst(it.pos, YELLOW, 20, glow=True)
        self.combo += 1
        self.combo_timer = self.stats["combo_window"]
        self.multiplier = self.multiplier_for()

    def start_wave(self):
        wl = self.world()
        count = 3 + int(self.wave * 0.9)
        if wl["gimmick"] == "overdrive":
            count = int(count * 1.35)
        elif wl["gimmick"] == "mines":
            count = int(count * 1.2)
        elif wl["gimmick"] == "pulse":
            count = int(count * 1.3)
        for _ in range(min(count, 22)):
            self.spawn_enemy()
        self.wave_banner = 1.6
        total = wl["waves"]
        self.banner_text = f"WAVE {self.wave}" + (f"/{total}" if total else "")
        if self.wave % 5 == 0 and self.lives < self.max_lives:
            self.lives += 1
            self.banner_text += "   +1 LIFE"

    def grant_xp(self, amount):
        self.xp += amount * self.stats["xp"] * XP_WORLD_MULT[self.meta.world]
        while self.xp >= xp_next(self.level) and self.level < 99:
            self.xp -= xp_next(self.level)
            self.level += 1
            self.levelups += 1
            self.player.level = self.level
            self.burst(self.player.pos, self.multiplier_color(), 14, glow=True)
        if self.levelups > 0 and self.state == "playing":
            self.open_levelup()

    def open_levelup(self):
        self.audio.levelup()
        pool = []
        for u in UPG_POOL:
            if self.run_upgrades[u["id"]] >= u["max"]:
                continue
            if u["id"] == "shieldc" and (self.stats["shield_max"] == 0 or self.shield_count >= self.stats["shield_max"]):
                continue
            if u["id"] == "heal" and self.lives >= self.max_lives:
                continue
            pool.append(u)
        if not pool:
            self.levelups -= 1
            self.state = "playing"
            return
        chosen = []
        tmp = list(pool)
        for _ in range(min(3, len(tmp))):
            wsum = sum(t["weight"] for t in tmp)
            r = random.uniform(0, wsum)
            acc = 0
            pick = tmp[-1]
            for t in tmp:
                acc += t["weight"]
                if r <= acc:
                    pick = t
                    break
            chosen.append(pick)
            tmp.remove(pick)
        self.levelup_options = chosen
        self.levelup_sel = 0
        self.state = "levelup"

    def choose_upgrade(self, i):
        if self.state != "levelup" or not self.levelup_options:
            return
        if not (0 <= i < len(self.levelup_options)):
            return
        opt = self.levelup_options[i]
        self.run_upgrades[opt["id"]] += 1
        if opt["id"] == "shieldc":
            self.shield_count = self.stats["shield_max"]
        if opt["id"] == "heal":
            self.lives = min(self.max_lives, self.lives + 1)
        self.levelups -= 1
        self.recompute_stats()
        self.player.move_mult = self.stats["move"]
        self.levelup_options = []
        self.state = "playing"
        self.audio.pickup()
        if self.levelups > 0:
            self.open_levelup()

    def kill_enemy(self, e):
        self.score += 100 * self.multiplier
        self.audio.explode()
        self.burst(e.pos, e.color, 16, glow=True)
        self.shake = min(self.shake + 6, 22)
        self.grant_xp(KILL_XP.get(e.kind, KILL_XP_DEFAULT))
        aw, ah = self.arena
        for _ in range(3):
            sp = e.pos + np.random.uniform(-6, 6, 2)
            sp[0] = np.clip(sp[0], 24, aw - 24)
            sp[1] = np.clip(sp[1], 24, ah - 24)
            self.shards.append(Shard(sp))

    def burst(self, pos, color, n, glow=False):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(40, 280)
            self.particles.append({
                "x": pos[0], "y": pos[1],
                "vx": math.cos(a) * sp, "vy": math.sin(a) * sp,
                "t": random.uniform(0.25, 0.8), "color": color, "glow": glow,
            })

    def damage_player(self):
        if self.hit_i > 0:
            return
        self.hit_i = HIT_INVULN
        if self.shield_count > 0:
            self.shield_count -= 1
            self.audio.hit()
            self.player.hit_flash = 0.25
            self.shake = min(self.shake + 14, 26)
            self.flash = 0.25
            self.burst(self.player.pos, CYAN, 18, glow=True)
            self.combo = 0
            self.multiplier = 1
            for e in self.enemies:
                e.pos += (e.pos - self.player.pos) * 0.02
            return
        self.lives -= 1
        self.audio.hit()
        self.player.hit_flash = 0.35
        self.shake = min(self.shake + 18, 30)
        self.flash = 0.35
        self.burst(self.player.pos, RED, 24, glow=True)
        self.combo = 0
        self.multiplier = 1
        if self.lives > 0:
            for e in self.enemies:
                e.pos += (e.pos - self.player.pos) * 0.02

    # ---------------- drawing ----------------
    def draw_bg(self, beat):
        wl = self.world()
        self.screen.fill(wl["bg"])
        step = 64.0
        off = (self.t * 30) % step
        pulse = 0.30 + 0.7 * (1.0 - beat)
        g = wl["grid"]
        col = (min(255, int(g[0] * pulse) + 10), min(255, int(g[1] * pulse) + 10), min(255, int(g[2] * pulse) + 10))
        cam = [self.cam[0], self.cam[1]]
        if self.shake > 0:
            cam[0] += random.uniform(-self.shake, self.shake) * 0.5
            cam[1] += random.uniform(-self.shake, self.shake) * 0.5
        x = -(cam[0] % step) + off
        while x <= W:
            pygame.draw.line(self.screen, col, (x, 0), (x, H), 1)
            x += step
        y = -(cam[1] % step) + off
        while y <= H:
            pygame.draw.line(self.screen, col, (0, y), (W, y), 1)
            y += step
        self.stars.update_draw(self.screen, 1 / FPS, [0, 0], wl["star"])

    def draw_waveform(self, beat):
        wl = self.world()
        band_top = H - 120
        ov = pygame.Surface((W, H - (band_top - 4)), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        self.screen.blit(ov, (0, band_top - 4))
        f = self.audio.root_hz() if not self.audio.MUTE else 110.0
        n = 140
        t = np.linspace(0, 2.2, n)
        ph = self.t * 0.8
        w = (0.6 * np.sin(2 * np.pi * f * t + ph) +
             0.25 * np.sin(2 * np.pi * f * 2 * t + ph * 1.3) +
             0.15 * np.sin(2 * np.pi * f * 3 * t))
        amp = 22 + 26 * (1.0 - beat)
        pts = []
        for i in range(n):
            x = 20 + i * (W - 40) / (n - 1)
            y = H - 62 + w[i] * amp
            pts.append((x, y))
        pygame.draw.lines(self.screen, wl["wave"], False, pts, 3)
        for gx, gy in pts[::2]:
            Glow.circle(self.screen, (gx, gy), 3, wl["wave"], 1)
        pygame.draw.line(self.screen, (40, 50, 70), (20, H - 62), (W - 20, H - 62), 1)

    def draw_particles(self, cam):
        for pt in self.particles:
            col = pt["color"]
            pos = (int(pt["x"] - cam[0]), int(pt["y"] - cam[1]))
            r = 2 if not pt.get("glow") else 4
            pygame.draw.circle(self.screen, col, pos, r)
            if pt.get("glow"):
                Glow.circle(self.screen, (pt["x"] - cam[0], pt["y"] - cam[1]), 6, col, 1)

    def draw_hud(self):
        wl = self.world()
        hx, hy = 18, 14
        txt = [
            f"SCORE  {self.score}",
            f"LIVES  {max(self.lives, 0)}",
            f"WAVE   {self.wave}",
            f"LV {self.level}   x{self.multiplier}",
        ]
        for i, t in enumerate(txt):
            col = self.multiplier_color() if i == 3 else WHITE
            self.screen.blit(self.font.render(t, True, col), (hx, hy + i * 30))
        wname = self.smallfont.render(f"{wl['name']}", True, wl["accent"])
        self.screen.blit(wname, wname.get_rect(topright=(W - 18, 14)))
        xp_w = 220
        xp_y = hy + 128
        need = xp_next(self.level)
        frac = min(1.0, self.xp / need)
        pygame.draw.rect(self.screen, (30, 40, 60), (hx, xp_y, xp_w, 8), 1)
        pygame.draw.rect(self.screen, (140, 200, 255), (hx, xp_y, int(xp_w * frac), 8))
        self.screen.blit(self.smallfont.render("XP", True, (120, 160, 200)), (hx, xp_y + 12))
        bar_y = xp_y + 30
        pygame.draw.rect(self.screen, (30, 40, 60), (hx, bar_y, xp_w, 10), 1)
        fill = int(xp_w * self.charge)
        if fill:
            pygame.draw.rect(self.screen, self.multiplier_color(), (hx, bar_y, fill, 10))
        self.screen.blit(self.smallfont.render("CORE CHARGE", True, (120, 160, 200)), (hx, bar_y + 14))
        if self.stats["shield_max"] > 0:
            sy = bar_y + 32
            self.screen.blit(self.smallfont.render("SHIELD", True, (120, 160, 200)), (hx, sy))
            for i in range(self.stats["shield_max"]):
                col = CYAN if i < self.shield_count else (30, 40, 60)
                pygame.draw.circle(self.screen, col, (hx + 54 + i * 18, sy + 8), 6)

    def draw_menu(self):
        wl = self.world()
        beat = self.audio.beat_phase()
        self.draw_bg(beat)
        self.draw_waveform(beat)
        title = self.bigfont.render("SYNTHESIS", True, wl["accent"])
        r = title.get_rect(center=(W / 2, H * 0.2))
        Glow.circle(self.screen, (r.centerx, r.centery), 40, wl["accent"], 2)
        self.screen.blit(title, r)
        sub = self.font.render("RESONANCE PROTOCOL", True, (160, 200, 230))
        self.screen.blit(sub, sub.get_rect(center=(W / 2, H * 0.2 + 56)))
        items = ["PLAY", "UPGRADES", "WORLDS"]
        for i, item in enumerate(items):
            col = YELLOW if i == self.menu_sel else WHITE
            img = self.font.render(item, True, col)
            pos = (W / 2, H * 0.46 + i * 46)
            if i == self.menu_sel:
                Glow.circle(self.screen, pos, 14, YELLOW, 1)
            self.screen.blit(img, img.get_rect(center=pos))
        res = self.font.render(f"ESSENCE  {self.meta.resonance}    HEAT  {self.meta.heat()}    WORLD  {wl['name']}",
                               True, YELLOW)
        self.screen.blit(res, res.get_rect(center=(W / 2, H * 0.72)))
        hint = self.smallfont.render("UP/DOWN + ENTER   ESC: QUIT", True, (150, 180, 210))
        self.screen.blit(hint, hint.get_rect(center=(W / 2, H - 90)))

    def _shop_center(self):
        return (int(W / 2), 340)

    def _branch_angle(self, col):
        return col * (math.pi / 2) - (math.pi / 4)

    def _tier_radius(self, row):
        return 64 + row * 58

    def shop_pos(self, d):
        cx, cy = self._shop_center()
        ang = self._branch_angle(d["col"])
        wob = [-0.04, 0.06, -0.06, 0.04][d["row"]]
        if d["col"] % 2:
            wob = -wob
        ang += wob
        r = self._tier_radius(d["row"])
        return (int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang)))

    def _tree_curve(self, p0, p1):
        mx = (p0[0] + p1[0]) // 2 + (p1[0] - p0[0])
        my = (p0[1] + p1[1]) // 2
        pts = []
        for i in range(16):
            t = i / 15.0
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * mx + t * t * p1[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * my + t * t * p1[1]
            pts.append((int(x), int(y)))
        return pts

    def draw_shop(self):
        wl = self.world()
        ov = pygame.Surface((W, H))
        ov.set_alpha(215)
        ov.fill((3, 4, 8))
        self.screen.blit(ov, (0, 0))
        head = self.font.render("UPGRADE NODES", True, wl["accent"])
        self.screen.blit(head, head.get_rect(center=(W / 2, 34)))
        res = self.font.render(f"ESSENCE  {self.meta.resonance}    HEAT  {self.meta.heat()}", True, YELLOW)
        self.screen.blit(res, res.get_rect(center=(W / 2, 66)))
        hub = self._shop_center()
        pygame.draw.circle(self.screen, (60, 70, 100), hub, 8, 1)
        for rr in (68, 122, 236):
            pygame.draw.circle(self.screen, (40, 44, 66), hub, rr, 1)
        for d in Meta.DEFS:
            pygame.draw.line(self.screen, (32, 38, 58), hub, self.shop_pos(d), 1)
        for d in Meta.DEFS:
            pos = self.shop_pos(d)
            for pid, minlvl in d["pre"]:
                pd = next(x for x in Meta.DEFS if x["id"] == pid)
                ppos = self.shop_pos(pd)
                owned = self.meta.levels[pid] >= minlvl
                c = (90, 160, 120) if owned else (70, 70, 80)
                pygame.draw.lines(self.screen, c, False, self._tree_curve(ppos, pos), 2)
        for d in Meta.DEFS:
            pos = self.shop_pos(d)
            lvl = self.meta.lvl(d["id"])
            maxed = lvl >= d["max"]
            ok = self.meta.prereq_met(d)
            afford = self.meta.afford(d)
            if maxed:
                fill, bord = (50, 200, 180), (140, 255, 230)
            elif lvl > 0:
                fill, bord = (30, 90, 110), wl["accent"]
            elif ok and afford:
                fill, bord = (70, 60, 20), YELLOW
            elif ok:
                fill, bord = (30, 34, 48), (140, 150, 170)
            else:
                fill, bord = (20, 22, 30), (80, 80, 95)
            sel = i_for = None
            for idx, dd in enumerate(Meta.DEFS):
                if dd is d:
                    i_for = idx
            pygame.draw.circle(self.screen, fill, pos, 30)
            pygame.draw.circle(self.screen, bord, pos, 30, 3 if i_for != self.shop_sel else 5)
            if i_for == self.shop_sel:
                pygame.draw.circle(self.screen, YELLOW, pos, 37, 1)
            if maxed:
                t = self.smallfont.render("MAX", True, (0, 20, 20))
            else:
                t = self.smallfont.render(str(lvl), True, WHITE)
            self.screen.blit(t, t.get_rect(center=pos))
            if not maxed:
                cost = self.meta.cost(d)
                cc = YELLOW if (ok and afford) else (140, 140, 150)
                cimg = self.smallfont.render(f"{cost}", True, cc)
                self.screen.blit(cimg, cimg.get_rect(center=(pos[0], pos[1] + 46)))
        hub = self._shop_center()
        for i, b in enumerate(["CORE", "AEGIS", "FIELD", "VELOCITY"]):
            ang = self._branch_angle(i)
            rad = 264
            lab = self.smallfont.render(b, True, (150, 180, 210))
            self.screen.blit(lab, lab.get_rect(center=(int(hub[0] + rad * math.cos(ang)), int(hub[1] + rad * math.sin(ang)))))
        # info panel for selected node
        d = Meta.DEFS[self.shop_sel]
        lvl = self.meta.lvl(d["id"])
        maxed = lvl >= d["max"]
        pre_ok = self.meta.prereq_met(d)
        lines = [d["name"], d["desc"], f"LEVEL {lvl}/{d['max']}"]
        col = WHITE
        if not pre_ok:
            req = ", ".join(f"{next(x['name'] for x in Meta.DEFS if x['id']==pid)} {ml}" for pid, ml in d["pre"])
            lines.append(f"REQUIRES: {req}")
            col = (180, 120, 120)
        elif maxed:
            lines.append("MAXED")
            col = (120, 240, 200)
        elif self.meta.afford(d):
            lines.append(f"COST {self.meta.cost(d)} - PRESS ENTER")
            col = YELLOW
        else:
            lines.append(f"COST {self.meta.cost(d)}")
            col = (150, 150, 160)
        for j, ln in enumerate(lines):
            img = self.font.render(ln, True, col if j == 0 else WHITE)
            self.screen.blit(img, img.get_rect(center=(W / 2, H - 128 + j * 26)))
        hint = self.smallfont.render("ARROWS move   ENTER buy   B / ESC back", True, (150, 180, 210))
        self.screen.blit(hint, hint.get_rect(center=(W / 2, H - 22)))

    def draw_worlds(self):
        wl = self.world()
        ov = pygame.Surface((W, H))
        ov.set_alpha(215)
        ov.fill((3, 4, 8))
        self.screen.blit(ov, (0, 0))
        head = self.font.render("SELECT WORLD", True, wl["accent"])
        self.screen.blit(head, head.get_rect(center=(W / 2, 40)))
        for i, w in enumerate(WORLDS):
            y = 100 + i * 92
            sel = i == self.world_sel
            rect = pygame.Rect(W / 2 - 260, y, 520, 84)
            unlocked = i <= self.meta.worlds
            border = YELLOW if sel else (80, 90, 110)
            bg = (22, 26, 44) if sel else (10, 14, 26)
            pygame.draw.rect(self.screen, bg, rect)
            pygame.draw.rect(self.screen, border, rect, 3 if sel else 1)
            name = self.font.render(w["name"], True, w["accent"])
            self.screen.blit(name, (rect.left + 20, rect.top + 8))
            if i == self.meta.world:
                tag = self.smallfont.render("SELECTED", True, YELLOW)
                self.screen.blit(tag, (rect.right - 90, rect.top + 8))
            if unlocked:
                info = self.smallfont.render(f"{w['waves'] or 'ENDLESS'} waves   gimmick: {w['gimmick']}",
                                             True, (170, 190, 210))
                self.screen.blit(info, (rect.left + 20, rect.top + 40))
                if sel:
                    hint = self.smallfont.render("ENTER to select", True, YELLOW)
                    self.screen.blit(hint, (rect.right - 160, rect.top + 40))
            else:
                info = self.smallfont.render("LOCKED - clear the previous world", True, (150, 100, 100))
                self.screen.blit(info, (rect.left + 20, rect.top + 40))
        hint = self.smallfont.render("UP/DOWN select   ENTER choose   B / ESC back", True, (150, 180, 210))
        self.screen.blit(hint, hint.get_rect(center=(W / 2, H - 30)))

    def draw_levelup(self):
        wl = self.world()
        ov = pygame.Surface((W, H))
        ov.set_alpha(150)
        ov.fill((5, 5, 12))
        self.screen.blit(ov, (0, 0))
        head = self.font.render("LEVEL UP - CHOOSE AN UPGRADE", True, YELLOW)
        self.screen.blit(head, head.get_rect(center=(W / 2, H * 0.3)))
        cx = W / 2 - 330
        for i, opt in enumerate(self.levelup_options):
            x = cx + i * 330
            rect = pygame.Rect(x - 140, H * 0.4, 280, 190)
            sel = i == self.levelup_sel
            border = YELLOW if sel else (90, 100, 130)
            bg = (16, 22, 40) if sel else (10, 14, 28)
            pygame.draw.rect(self.screen, bg, rect)
            pygame.draw.rect(self.screen, border, rect, 3 if sel else 1)
            name = self.font.render(opt["name"], True, wl["accent"] if sel else WHITE)
            self.screen.blit(name, name.get_rect(center=(rect.centerx, rect.top + 30)))
            lvl = self.run_upgrades[opt["id"]]
            lv = self.smallfont.render(f"LV {lvl}" + (f"/{opt['max']}" if opt["max"] < 99 else ""), True, (150, 180, 210))
            self.screen.blit(lv, lv.get_rect(center=(rect.centerx, rect.top + 66)))
            for j, line in enumerate(wrap(opt["desc"], 26)):
                img = self.smallfont.render(line, True, WHITE)
                self.screen.blit(img, img.get_rect(center=(rect.centerx, rect.top + 104 + j * 22)))
        hint = self.smallfont.render("LEFT/RIGHT or 1/2/3   ENTER", True, (150, 180, 210))
        self.screen.blit(hint, hint.get_rect(center=(W / 2, H * 0.8)))

    def draw_gameover(self):
        wl = self.world()
        ov = pygame.Surface((W, H))
        ov.set_alpha(170)
        ov.fill((5, 5, 12))
        self.screen.blit(ov, (0, 0))
        if self.win:
            title = "WORLD CLEARED" if self.boss is None else "PROTOCOL ANCHOR DESTROYED"
            tcol = wl["accent"]
        else:
            title = "GAME OVER"
            tcol = RED
        img = self.bigfont.render(title, True, tcol)
        self.screen.blit(img, img.get_rect(center=(W / 2, H / 2 - 130)))
        info = f"SCORE  {self.score}    WAVE  {self.wave}    BEST  {self.record}"
        sub = self.font.render(info, True, WHITE)
        self.screen.blit(sub, sub.get_rect(center=(W / 2, H / 2 - 80)))
        if not self.world()["waves"]:
            sub2 = self.font.render("THIS WORLD IS ENDLESS", True, (170, 190, 210))
            self.screen.blit(sub2, sub2.get_rect(center=(W / 2, H / 2 - 40)))
        earn = self.font.render(f"+{self.essence_earned} ESSENCE", True, YELLOW)
        self.screen.blit(earn, earn.get_rect(center=(W / 2, H / 2 - 10)))
        if self.new_unlock:
            un = self.font.render(f"WORLD UNLOCKED: {self.new_unlock}", True, wl["accent"])
            self.screen.blit(un, un.get_rect(center=(W / 2, H / 2 + 30)))
        blink = "PRESS R TO RESTART      M: MENU"
        if int(self.t * 2) % 2 == 0:
            img = self.font.render(blink, True, YELLOW)
            self.screen.blit(img, img.get_rect(center=(W / 2, H / 2 + 70)))

    def draw(self):
        beat = self.audio.beat_phase()
        if self.state == "menu":
            self.draw_menu()
            pygame.display.flip()
            return
        if self.state == "shop":
            self.draw_bg(beat)
            self.draw_waveform(beat)
            self.draw_shop()
            pygame.display.flip()
            return
        if self.state == "worlds":
            self.draw_bg(beat)
            self.draw_waveform(beat)
            self.draw_worlds()
            pygame.display.flip()
            return

        self.draw_bg(beat)

        cam = [self.cam[0], self.cam[1]]
        if self.shake > 0:
            cam[0] += random.uniform(-self.shake, self.shake) * 0.5
            cam[1] += random.uniform(-self.shake, self.shake) * 0.5

        self.draw_particles(cam)

        wl = self.world()
        for s in self.shards:
            s.draw(self.screen, wl["wave"], cam)

        for it in self.items:
            it.draw(self.screen, cam)

        for e in self.enemies:
            e.draw(self.screen, cam)

        for m in self.mines:
            px = m["pos"][0] - cam[0]
            py = m["pos"][1] - cam[1]
            r = MINE_RADIUS + int(2 * math.sin(self.t * 6))
            pts = [(px + math.cos(i / 6 * math.tau) * r, py + math.sin(i / 6 * math.tau) * r) for i in range(6)]
            col = WHITE if m["t"] < 1.5 else wl["accent"]
            pygame.draw.polygon(self.screen, col, pts, 2)
            Glow.circle(self.screen, (px, py), MINE_RADIUS, wl["accent"], 1)

        for s in self.shots:
            s.draw(self.screen, cam)

        for s in self.boss_shots:
            s.draw(self.screen, cam)

        if self.boss and not self.boss.dead:
            self.boss.draw(self.screen, cam)

        for b in self.bolts:
            bx, by = int(b["pos"][0] - cam[0]), int(b["pos"][1] - cam[1])
            for seg in range(5):
                jx = bx + random.randint(-14, 14)
                jy = by + random.randint(-14, 14)
                pygame.draw.line(self.screen, (220, 190, 255), (bx, by), (jx, jy), 2)
            Glow.circle(self.screen, (bx, by), BOLT_RADIUS, (160, 130, 255), 2)
            Glow.circle(self.screen, (bx, by), 22, (255, 255, 255), 2)

        for pu in self.pulses:
            px = pu["pos"][0] - cam[0]
            py = pu["pos"][1] - cam[1]
            if pu["warn"] > 0:
                Glow.circle(self.screen, (px, py), 30, wl["accent"], 2)
            r = int(pu["r"])
            if r > 0:
                pygame.draw.circle(self.screen, wl["accent"], (int(px), int(py)), r, 2)
                Glow.circle(self.screen, (px, py), r, wl["accent"], 1)

        if self.player.alive:
            self.player.draw(self.screen, self.multiplier_color(), cam)
            if self.stats["shield_max"] > 0 and self.shield_count > 0:
                pp = (int(self.player.pos[0] - cam[0]), int(self.player.pos[1] - cam[1]))
                pygame.draw.circle(self.screen, CYAN, pp, self.player.radius + 16, 2)

        if self.flash > 0:
            ov = pygame.Surface((W, H))
            ov.set_alpha(int(255 * min(1.0, self.flash) * 0.5))
            ov.fill((255, 40, 40))
            self.screen.blit(ov, (0, 0))

        self.draw_waveform(beat)
        self.draw_hud()

        if self.boss and not self.boss.dead:
            frac = max(0.0, self.boss.hp / self.boss.maxhp)
            bw, bh = 480, 12
            bxr = (W - bw) // 2
            pygame.draw.rect(self.screen, (30, 30, 40), (bxr, 58, bw, bh))
            fill = int(bw * frac)
            if fill:
                pygame.draw.rect(self.screen, (255, 60, 60), (bxr, 58, fill, bh))
            pygame.draw.rect(self.screen, (255, 140, 140), (bxr, 58, bw, bh), 1)
            lab = self.smallfont.render(f"{self.boss.name}  {int(self.boss.hp)}/{self.boss.maxhp}", True, (255, 160, 160))
            self.screen.blit(lab, lab.get_rect(center=(W / 2, 40)))

        if self.overdrive_t > 0:
            lab = self.smallfont.render(f"OVERDRIVE  {self.overdrive_t:.1f}s", True, ORANGE)
            self.screen.blit(lab, lab.get_rect(center=(W / 2, 86)))

        if self.wave_banner > 0:
            img = self.bigfont.render(self.banner_text, True, WHITE)
            r = img.get_rect(center=(W / 2, H * 0.32))
            self.screen.blit(img, r)

        if self.state == "over":
            self.draw_gameover()
        elif self.state == "levelup":
            self.draw_levelup()

        pygame.display.flip()

    def shop_move(self, dx, dy):
        cur = self.shop_pos(Meta.DEFS[self.shop_sel])
        best = None
        bestd = None
        for i, d in enumerate(Meta.DEFS):
            if i == self.shop_sel:
                continue
            p = self.shop_pos(d)
            if dx > 0 and p[0] <= cur[0]:
                continue
            if dx < 0 and p[0] >= cur[0]:
                continue
            if dy > 0 and p[1] <= cur[1]:
                continue
            if dy < 0 and p[1] >= cur[1]:
                continue
            dist = math.hypot(p[0] - cur[0], p[1] - cur[1])
            if bestd is None or dist < bestd:
                bestd = dist
                best = i
        if best is not None:
            self.shop_sel = best

    def shop_buy(self):
        d = Meta.DEFS[self.shop_sel]
        if self.meta.lvl(d["id"]) >= d["max"]:
            self.audio.hit()
            return
        if not self.meta.prereq_met(d):
            self.audio.hit()
            return
        c = self.meta.cost(d)
        if self.meta.resonance < c:
            self.audio.hit()
            return
        self.meta.resonance -= c
        self.meta.levels[d["id"]] += 1
        self.meta.save()
        self.recompute_stats()
        self.audio.pickup()

    def start_game(self):
        self.state = "playing"
        self.reset()

    def run(self):
        try:
            while True:
                dt = self.clock.tick(FPS) / 1000.0
                dt = min(dt, 0.05)
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        raise SystemExit
                    if ev.type == pygame.MOUSEMOTION:
                        self.last_mouse = np.array(ev.pos, dtype=float)
                        self.last_mouse_t = self.t
                    if ev.type == pygame.KEYDOWN:
                        k = ev.key
                        if k == pygame.K_ESCAPE:
                            if self.state == "shop" or self.state == "worlds":
                                self.state = "menu"
                            else:
                                raise SystemExit
                        if self.state == "menu":
                            if k in (pygame.K_UP, pygame.K_w):
                                self.menu_sel = (self.menu_sel - 1) % 3
                            elif k in (pygame.K_DOWN, pygame.K_s):
                                self.menu_sel = (self.menu_sel + 1) % 3
                            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                                if self.menu_sel == 0:
                                    self.start_game()
                                elif self.menu_sel == 1:
                                    self.shop_sel = 0
                                    self.state = "shop"
                                else:
                                    self.world_sel = self.meta.world
                                    self.state = "worlds"
                        elif self.state == "shop":
                            if k in (pygame.K_UP, pygame.K_w):
                                self.shop_move(0, -1)
                            elif k in (pygame.K_DOWN, pygame.K_s):
                                self.shop_move(0, 1)
                            elif k in (pygame.K_LEFT, pygame.K_a):
                                self.shop_move(-1, 0)
                            elif k in (pygame.K_RIGHT, pygame.K_d):
                                self.shop_move(1, 0)
                            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                                self.shop_buy()
                            elif k in (pygame.K_b, pygame.K_ESCAPE):
                                self.state = "menu"
                        elif self.state == "worlds":
                            if k in (pygame.K_UP, pygame.K_w):
                                self.world_sel = (self.world_sel - 1) % len(WORLDS)
                            elif k in (pygame.K_DOWN, pygame.K_s):
                                self.world_sel = (self.world_sel + 1) % len(WORLDS)
                            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                                if self.world_sel <= self.meta.worlds:
                                    self.meta.world = self.world_sel
                                    self.meta.save()
                                    self.state = "menu"
                            elif k in (pygame.K_b, pygame.K_ESCAPE):
                                self.state = "menu"
                        elif self.state == "levelup":
                            if k in (pygame.K_1,):
                                self.choose_upgrade(0)
                            elif k in (pygame.K_2,):
                                self.choose_upgrade(1)
                            elif k in (pygame.K_3,):
                                self.choose_upgrade(2)
                            elif k in (pygame.K_LEFT, pygame.K_a):
                                self.levelup_sel = (self.levelup_sel - 1) % len(self.levelup_options)
                            elif k in (pygame.K_RIGHT, pygame.K_d):
                                self.levelup_sel = (self.levelup_sel + 1) % len(self.levelup_options)
                            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                                self.choose_upgrade(self.levelup_sel)
                        elif self.state == "over":
                            if k == pygame.K_r:
                                self.start_game()
                            if k == pygame.K_m:
                                self.state = "menu"
                self.update(dt)
                self.draw()
        except SystemExit:
            pass
        finally:
            self.audio.stop()
            self.meta.save()
            pygame.quit()
            sys.exit()


if __name__ == "__main__":
    Game().run()
