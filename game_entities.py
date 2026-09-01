import math
import random

import numpy as np
import pygame

from game_defs import (W, H, PLAYER_ACCEL, PLAYER_FRICTION, PLAYER_MAX_SPEED,
                       PLAYER_RADIUS, SHARD_LIFE, CYAN, RED, WHITE, GREEN,
                       BOSS_ATTACK, BOSS_WINDUP, BOSS_ATTACK_INTERVAL,
                       GLOW_MAX_RADIUS)


class Starfield:
    def __init__(self):
        self.layers = []
        for speed, n in ((12, 60), (28, 42), (55, 26)):
            stars = [(random.uniform(0, W), random.uniform(0, H),
                      random.uniform(0.4, 1.0), (200, 210, 255))
                     for _ in range(n)]
            self.layers.append((speed, stars))

    def update_draw(self, surf, dt, cam, colors):
        for speed, stars in self.layers:
            for i, (x, y, b, _) in enumerate(stars):
                y += speed * dt
                x += speed * dt * 0.4
                if y > H + 2:
                    y = -2
                    x = random.uniform(0, W)
                if x > W + 2:
                    x = -2
                stars[i] = (x, y, b, colors[i % len(colors)])
                pygame.draw.circle(surf, stars[i][3], (int(x + cam[0]), int(y + cam[1])), max(1, int(b * 1.6)))


class Glow:
    @staticmethod
    def circle(surf, pos, radius, color, intensity):
        radius = max(1, min(int(radius), GLOW_MAX_RADIUS))
        for i in range(3, 0, -1):
            r = int(radius * (1 + i * 0.7))
            a = int(intensity * (255 // 4) * (i / 3))
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, a), (r, r), r)
            surf.blit(s, (pos[0] - r, pos[1] - r), special_flags=pygame.BLEND_ADD)


class Player:
    def __init__(self, x, y):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([0.0, 0.0])
        self.radius = PLAYER_RADIUS
        self.move_mult = 1.0
        self.level = 1
        self.fire_timer = 0.0
        self.hit_flash = 0.0
        self.alive = True

    def update(self, dt, keys, bounds=(W, H)):
        dir_ = np.array([0.0, 0.0])
        if keys[pygame.K_a]:
            dir_[0] -= 1
        if keys[pygame.K_d]:
            dir_[0] += 1
        if keys[pygame.K_w]:
            dir_[1] -= 1
        if keys[pygame.K_s]:
            dir_[1] += 1
        if math.hypot(dir_[0], dir_[1]) > 0:
            dir_ = dir_ / math.hypot(dir_[0], dir_[1])
            self.vel += dir_ * PLAYER_ACCEL * self.move_mult * dt
        self.vel *= PLAYER_FRICTION
        spd = math.hypot(self.vel[0], self.vel[1])
        max_spd = PLAYER_MAX_SPEED * self.move_mult
        if spd > max_spd:
            self.vel *= max_spd / spd
        self.pos += self.vel * dt
        bw, bh = bounds
        self.pos[0] = np.clip(self.pos[0], self.radius, bw - self.radius)
        self.pos[1] = np.clip(self.pos[1], self.radius, bh - self.radius)
        self.fire_timer = max(0.0, self.fire_timer - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)

    def can_fire(self):
        return self.fire_timer <= 0

    def draw(self, surf, color=CYAN, cam=(0, 0)):
        p = self.pos - np.array(cam, dtype=float)
        flash = self.hit_flash > 0
        core = RED if flash else color
        r = self.radius + min(7, (self.level - 1) // 3)
        Glow.circle(surf, (p[0], p[1]), r + 4, core, 2)
        pygame.draw.circle(surf, (200, 255, 255), p.astype(int), r + 10)
        pygame.draw.circle(surf, (120, 240, 255), p.astype(int), r + 5)
        pygame.draw.circle(surf, core, p.astype(int), r)


class Projectile:
    def __init__(self, pos, vel, damage=1.0, pierce=0, homing=False, color=CYAN):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.array(vel, dtype=float)
        self.speed = math.hypot(self.vel[0], self.vel[1])
        self.radius = 4
        self.color = color
        self.damage = damage
        self.pierce = pierce
        self.homing = homing
        self.dead = False

    def steer(self, enemies):
        if not self.homing or not enemies:
            return
        best, nd = None, 1e18
        for e in enemies:
            d = math.hypot(e.pos[0] - self.pos[0], e.pos[1] - self.pos[1])
            if d < nd:
                nd, best = d, e
        if best is None or nd < 1:
            return
        d = (best.pos - self.pos) / nd
        self.vel = self.vel + d * 520.0
        sp = math.hypot(self.vel[0], self.vel[1])
        if sp < 1:
            sp = 1
        self.vel = self.vel / sp * self.speed

    def update(self, dt, bounds=(W, H)):
        self.pos += self.vel * dt
        bw, bh = bounds
        if (self.pos[0] < -20 or self.pos[0] > bw + 20
                or self.pos[1] < -20 or self.pos[1] > bh + 20):
            self.dead = True

    def draw(self, surf, cam=(0, 0)):
        p = self.pos - np.array(cam, dtype=float)
        Glow.circle(surf, (p[0], p[1]), 6, self.color, 1)
        pygame.draw.circle(surf, self.color, p.astype(int), self.radius)
        pygame.draw.circle(surf, WHITE, p.astype(int), 2)


class Enemy:
    def __init__(self, kind, pos, speed, hp, color):
        self.kind = kind
        self.pos = np.array(pos, dtype=float)
        self.vel = np.array([0.0, 0.0])
        self.speed = speed
        self.hp = hp
        self.maxhp = hp
        self.color = color
        self.radius = 16 if kind == "chaser" else (13 if kind == "liner" else 15)
        self.phase = random.uniform(0, math.tau)
        self.dead = False

    def update(self, dt, player, bounds=(W, H)):
        if self.kind == "chaser":
            d = player.pos - self.pos
            nd = math.hypot(d[0], d[1])
            if nd > 1:
                self.vel = d / nd * self.speed
        elif self.kind == "liner":
            if math.hypot(self.vel[0], self.vel[1]) < 1:
                self.vel = np.array([1.0, 0.0]) * self.speed
        else:
            if math.hypot(self.vel[0], self.vel[1]) < 1:
                ang = random.uniform(0, math.tau)
                self.vel = np.array([math.cos(ang), math.sin(ang)]) * self.speed * 0.6
            self.phase += dt * 3.0
            perp = np.array([-self.vel[1], self.vel[0]]) / max(math.hypot(self.vel[0], self.vel[1]), 1)
            self.pos += perp * math.sin(self.phase) * self.speed * 0.9 * dt
        self.pos += self.vel * dt
        bw, bh = bounds
        if (self.pos[0] < -60 or self.pos[0] > bw + 60
                or self.pos[1] < -60 or self.pos[1] > bh + 60):
            self.dead = True

    def draw(self, surf, cam=(0, 0)):
        c = np.array(cam, dtype=float)
        px = self.pos[0] - c[0]
        py = self.pos[1] - c[1]
        n = {"chaser": 3, "liner": 4, "drifter": 5}[self.kind]
        pts = []
        for i in range(n):
            a = i / n * math.tau + self.phase * (0.5 if self.kind == "drifter" else 1.0)
            r = self.radius + (3 if i % 2 == 0 else -2)
            pts.append((px + math.cos(a) * r, py + math.sin(a) * r))
        Glow.circle(surf, (px, py), self.radius, self.color, 1)
        pygame.draw.polygon(surf, self.color, pts, 0)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        if self.hp < self.maxhp:
            frac = self.hp / self.maxhp
            w = self.radius * 2
            pygame.draw.rect(surf, (40, 40, 50), (int(px - self.radius), int(py - self.radius - 8), w, 3))
            pygame.draw.rect(surf, GREEN, (int(px - self.radius), int(py - self.radius - 8), int(w * frac), 3))


class Shard:
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.array([random.uniform(-60, 60), random.uniform(-60, 60)])
        self.life = SHARD_LIFE
        self.dead = False
        self.hue = random.random()

    def update(self, dt, player, magnet=160.0):
        d = player.pos - self.pos
        dist = math.hypot(d[0], d[1])
        if dist > 1:
            pull = d / dist
            if dist < magnet:
                self.vel += pull * 800 * dt
            else:
                self.vel += pull * 90 * dt
        self.vel *= 0.98
        self.pos += self.vel * dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
        if dist < player.radius + 8:
            self.dead = True
            return True
        return False

    def draw(self, surf, color, cam=(0, 0)):
        a = int(255 * min(1.0, self.life / 2.0))
        col = (min(255, 120 + int(135 * self.hue)), 240, 255)
        p = self.pos - np.array(cam, dtype=float)
        Glow.circle(surf, (p[0], p[1]), 5, col, 1)
        pygame.draw.circle(surf, (*col, a), p.astype(int), 3)


class Boss:
    def __init__(self, pos, hp, color, world_id=0, name="PROTOCOL ANCHOR"):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.array([0.0, 0.0])
        self.hp = hp
        self.maxhp = hp
        self.radius = 48
        self.color = color
        self.world_id = world_id
        self.name = name
        self.speed = 95
        self.phase = random.uniform(0, math.tau)
        self.spawn_t = 5.0
        self.dead = False
        self.at = 2.5
        self.move = -1
        self.windup = 0.0
        self.kind = None
        self.aim_angle = 0.0
        self.pending_shots = []
        self._spawn = []
        self._spawn_kind = "chaser"
        if world_id in BOSS_ATTACK:
            self.spawn_t = 9999.0

    def _pick_move(self, wl):
        self.move = (self.move + 1) % 3
        keys = list(wl.keys())
        return keys[self.move]

    def update(self, dt, player, bounds=(W, H)):
        self._bounds = bounds
        d = player.pos - self.pos
        nd = math.hypot(d[0], d[1])
        wl = BOSS_ATTACK.get(self.world_id)
        if wl is not None:
            self.at -= dt
            if self.at <= 0 and self.windup <= 0:
                self.windup = BOSS_WINDUP
                self.kind = self._pick_move(wl)
                self.aim_angle = math.atan2(d[1], d[0]) if nd > 1 else 0.0
            if self.windup > 0:
                self.windup -= dt
                self.vel[:] = 0.0
                if self.kind == "fan" or self.kind == "triple":
                    self.aim_angle = math.atan2(d[1], d[0]) if nd > 1 else self.aim_angle
                if self.windup <= 0:
                    self.release(wl)
            else:
                if nd > 1:
                    self.vel = d / nd * self.speed
                self.vel *= 0.9
        else:
            if nd > 1:
                self.vel = d / nd * self.speed
            self.vel *= 0.9
            self.spawn_t -= dt
            if self.spawn_t <= 0:
                self.spawn_t = 6.0
                self._spawn = [self.pos + np.array([-48, 50]), self.pos + np.array([48, 50])]
        self.pos += self.vel * dt
        bw, bh = bounds
        self.pos[0] = np.clip(self.pos[0], self.radius, bw - self.radius)
        self.pos[1] = np.clip(self.pos[1], self.radius, bh - self.radius)
        self.phase += dt * 2
        spawn = self._spawn
        self._spawn = []
        return spawn

    def release(self, wl):
        m = wl[self.kind]
        px, py = self.pos
        if self.kind == "fan" or self.kind == "triple":
            a0 = self.aim_angle - m["spread"] / 2
            for i in range(m["n"]):
                a = a0 + m["spread"] * i / max(m["n"] - 1, 1)
                self.pending_shots.append(
                    np.array([math.cos(a), math.sin(a)]) * m["speed"])
        elif self.kind == "ring" or self.kind == "rings":
            n = m["n"]
            off = 0.0
            for rep in range(2 if m.get("double") else 1):
                for i in range(n):
                    a = off + math.tau * i / n
                    self.pending_shots.append(
                        np.array([math.cos(a), math.sin(a)]) * m["speed"])
                off = math.pi / n
        elif self.kind == "summon":
            count = m["count"]
            self._spawn_kind = m.get("kind", "chaser")
            bw, bh = getattr(self, "_bounds", (1920, 1080))
            for i in range(count):
                a = math.tau * (i + 0.5) / count
                p = self.pos + np.array([math.cos(a), math.sin(a)]) * 70.0
                p[0] = np.clip(p[0], 30, bw - 30)
                p[1] = np.clip(p[1], 30, bh - 30)
                self._spawn.append(p)
        self.windup = 0.0
        self.kind = None
        self.at = BOSS_ATTACK_INTERVAL

    def set_bounds(self, bounds=(1920, 1080)):
        self._bounds = bounds

    def draw(self, surf, cam=(0, 0)):
        c = np.array(cam, dtype=float)
        px = self.pos[0] - c[0]
        py = self.pos[1] - c[1]
        n = 6
        pts = []
        for i in range(n):
            a = i / n * math.tau + self.phase
            r = self.radius + (6 if i % 2 == 0 else -4)
            pts.append((px + math.cos(a) * r, py + math.sin(a) * r))
        Glow.circle(surf, (px, py), self.radius + 6, self.color, 3)
        pygame.draw.polygon(surf, self.color, pts, 0)
        pygame.draw.polygon(surf, WHITE, pts, 2)
        pygame.draw.circle(surf, (255, 255, 255), (int(px), int(py)), 10, 2)
        if self.windup > 0 and self.kind is not None:
            frac = max(0.0, 1.0 - self.windup / BOSS_WINDUP)
            wl = BOSS_ATTACK.get(self.world_id, {})
            m = wl.get(self.kind, {})
            if self.kind in ("fan", "triple"):
                ln = 260.0
                ex = px + math.cos(self.aim_angle) * ln
                ey = py + math.sin(self.aim_angle) * ln
                pygame.draw.line(surf, WHITE, (px, py), (ex, ey), 2)
            elif self.kind in ("ring", "rings"):
                rr = m.get("ring_r", 90.0)
                pygame.draw.circle(surf, WHITE, (int(px), int(py)), int(rr), 2)
            elif self.kind == "summon":
                count = m.get("count", 3)
                for i in range(count):
                    a = math.tau * (i + 0.5) / count
                    sx = px + math.cos(a) * 70.0
                    sy = py + math.sin(a) * 70.0
                    pygame.draw.circle(surf, WHITE, (int(sx), int(sy)), 6, 1)
            pygame.draw.circle(surf, (255, 255, 255), (int(px), int(py)),
                               int(self.radius + 8 * frac), 2)


class Item:
    def __init__(self, pos, itype, ttype):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.array([0.0, 0.0])
        self.itype = itype
        self.ttype = ttype
        self.life = 9.0
        self.dead = False
        self.phase = random.uniform(0, math.tau)

    def update(self, dt, wind=(0.0, 0.0), player=None, magnet=160.0):
        if player is not None:
            d = player.pos - self.pos
            dist = math.hypot(d[0], d[1])
            if dist > 1:
                pull = d / dist
                if dist < magnet:
                    self.vel += pull * 800 * dt
                else:
                    self.vel += pull * 60 * dt
            self.vel *= 0.98
            self.pos += self.vel * dt
        self.pos += np.array(wind, dtype=float) * dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
        self.phase += dt * 4

    def draw(self, surf, cam=(0, 0)):
        p = self.pos - np.array(cam, dtype=float)
        col = self.ttype["color"]
        r = 11 + int(3 * math.sin(self.phase))
        Glow.circle(surf, (p[0], p[1]), r + 4, col, 2)
        pygame.draw.circle(surf, col, p.astype(int), r, 2)
        pygame.draw.circle(surf, WHITE, p.astype(int), r - 5, 1)
