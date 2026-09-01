import math
import random
import threading
import time

import numpy as np
import pygame

import game_defs

SR = game_defs.SR


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def to_sound(wave):
    wave = np.asarray(wave, dtype=np.float64)
    if wave.size == 0:
        wave = np.zeros(1)
    if np.max(np.abs(wave)) > 0:
        wave = wave / np.max(np.abs(wave))
    wave = np.clip(wave, -1.0, 1.0)
    fade = min(len(wave), int(0.006 * SR))
    if fade:
        env = np.ones(len(wave))
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        wave = wave * env
    n = len(wave)
    stereo = np.zeros((n, 2), dtype=np.float64)
    stereo[:, 0] = wave
    stereo[:, 1] = wave
    data = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(data)


def sine(freq, ms, vol=1.0, vib=0.0):
    n = int(SR * ms / 1000)
    t = np.arange(n) / SR
    if vib:
        t = t + (vib / (2 * math.pi * freq)) * np.sin(2 * math.pi * 6 * t)
    return vol * np.sin(2 * math.pi * freq * t)


def saw(freq, ms, vol=1.0):
    n = int(SR * ms / 1000)
    t = np.arange(n) / SR
    ph = (freq * t) % 1.0
    return vol * (2 * ph - 1)


def square(freq, ms, vol=1.0):
    n = int(SR * ms / 1000)
    t = np.arange(n) / SR
    return vol * np.sign(np.sin(2 * math.pi * freq * t))


def noise(ms, vol=1.0):
    n = int(SR * ms / 1000)
    return vol * np.random.uniform(-1, 1, n)


class AudioEngine:
    BPM = 104
    SPB = 60.0 / BPM
    STEP = SPB / 4.0

    ROOTS = [110.0, 110.0, 130.81, 130.81, 164.81, 164.81, 196.0, 196.0,
             87.31, 87.31, 110.0, 130.81, 98.0, 98.0, 123.47, 146.83]
    ARP = [220.0, 329.63, 440.0, 523.25, 659.26, 523.25]
    LEAD = [440.0, 523.25, 587.33, 659.26, 783.99, 659.26, 587.33, 523.25]

    def __init__(self):
        self.MUTE = False
        self.state = {"charge": 0.0, "combo": 0}
        self._running = False
        self._t0 = 0.0
        self._chan_idx = 0
        if game_defs.HEADLESS:
            self.MUTE = True
            return
        try:
            pygame.mixer.quit()
            pygame.mixer.pre_init(SR, -16, 2, 256)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
        except Exception:
            self.MUTE = True
            print("MUTE: no audio device")
            return
        self._build_sounds()
        self._build_layers()
        self._running = True
        self._t0 = time.perf_counter()
        self._step = 0
        self._next_t = self._t0
        self._thread = threading.Thread(target=self._scheduler, daemon=True)
        self._thread.start()

    def _build_sounds(self):
        self.bass = []
        for f in self.ROOTS:
            w = 0.55 * saw(f, 170) + 0.45 * sine(f, 170)
            w = w * np.exp(-np.arange(int(SR * 0.17)) / SR * 12)
            self.bass.append(to_sound(w))
        self.arp = []
        for f in self.ARP:
            w = 0.8 * sine(f, 130) + 0.2 * square(f, 130, 0.4)
            w = w * np.exp(-np.arange(int(SR * 0.13)) / SR * 10)
            self.arp.append(to_sound(w))
        self.lead = []
        for f in self.LEAD:
            w = 0.7 * sine(f, 240, vib=4.0) + 0.3 * saw(f * 2, 240, 0.25)
            w = w * np.exp(-np.arange(int(SR * 0.24)) / SR * 4)
            self.lead.append(to_sound(w))
        n = int(SR * 0.22)
        t = np.arange(n) / SR
        kf = 130.0 * np.exp(-t * 22) + 45.0
        kick = np.sin(2 * math.pi * np.cumsum(kf) / SR) * np.exp(-t * 14)
        self.kick = to_sound(kick * 1.0)
        n = int(SR * 0.05)
        t = np.arange(n) / SR
        hat = np.diff(np.concatenate(([0.0], noise(50)))) * np.exp(-t * 90)
        self.hat = to_sound(hat * 1.0)
        self.hat_long = to_sound(noise(120) * np.exp(-np.arange(int(SR * 0.12)) / SR * 30))
        n = int(SR * 0.09)
        t = np.arange(n) / SR
        w = np.sin(2 * math.pi * (900 + 2600 * t) * t) * np.exp(-t * 30)
        self.s_shoot = to_sound(w * 0.5)
        n = int(SR * 0.16)
        t = np.arange(n) / SR
        w = square(160, 160, 0.6) * np.exp(-t * 20)
        self.s_hit = to_sound(w * 0.7)
        n = int(SR * 0.5)
        t = np.arange(n) / SR
        boom = np.sin(2 * math.pi * np.cumsum(120 * np.exp(-t * 8) + 40) / SR)
        w = 0.6 * boom * np.exp(-t * 8) + 0.6 * noise(500)[:n] * np.exp(-t * 12)
        self.s_boom = to_sound(w * 0.8)
        n = int(SR * 0.12)
        t = np.arange(n) / SR
        w = (sine(880, 120) + 0.6 * sine(1320, 120)) * np.exp(-t * 18)
        self.s_pick = to_sound(w * 0.5)
        seg = [sine(523.25, 120, 0.4), sine(659.26, 120, 0.4), sine(783.99, 160, 0.4)]
        gap = np.zeros(int(SR * 0.04))
        w = np.concatenate([seg[0], gap, seg[1], gap, seg[2]])
        self.s_level = to_sound(w)

    def _build_layers(self):
        self.chans = {}
        for name in ("bass", "arp", "lead", "perc"):
            self.chans[name] = [pygame.mixer.Channel(i) for i in
                                ({"bass": 0, "arp": 2, "lead": 4, "perc": 6}[name] + j for j in (0, 1))]

    def _scheduler(self):
        while self._running:
            now = time.perf_counter()
            while self._next_t <= now:
                self._tick(self._step)
                self._step += 1
                self._next_t += self.STEP
            time.sleep(0.005)

    def _layer_play(self, name, sound, vol):
        if self.MUTE:
            return
        idx = self._chan_idx
        self._chan_idx ^= 1
        ch = self.chans[name][idx]
        ch.set_volume(vol)
        ch.play(sound)

    def _tick(self, step):
        st = self.state
        s = step % 16
        q = step % 4
        e = step % 2
        charge = st["charge"]
        combo = st["combo"]
        if q == 0:
            self._layer_play("perc", self.kick, 0.9)
        if e == 0:
            self._layer_play("bass", self.bass[s], 0.55)
        if charge > 0.03 and e == 0:
            idx = (step // 2) % len(self.ARP)
            self._layer_play("arp", self.arp[idx], 0.5 * charge)
        if charge > 0.55 and q == 0 and random.random() < 0.75:
            idx = (step // 4) % len(self.LEAD)
            self._layer_play("lead", self.lead[idx], 0.4 * (charge - 0.5))
        if combo > 0:
            if e == 1:
                self._layer_play("perc", self.hat, 0.25)
            if q == 2 and random.random() < 0.6:
                self._layer_play("perc", self.hat_long, 0.2)

    def set_state(self, charge, combo):
        self.state["charge"] = max(0.0, min(1.0, charge))
        self.state["combo"] = max(0, combo)

    def beat_phase(self):
        if self.MUTE:
            return 0.0
        pos = time.perf_counter() - self._t0
        return (pos / self.STEP) % 4.0 / 4.0

    def root_hz(self):
        step = int((time.perf_counter() - self._t0) / self.STEP)
        return self.ROOTS[step % 16]

    def shoot(self):
        if not self.MUTE:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(self.s_shoot)

    def hit(self):
        if not self.MUTE:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(self.s_hit)

    def explode(self):
        if not self.MUTE:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(self.s_boom)

    def pickup(self):
        if not self.MUTE:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(self.s_pick)

    def levelup(self):
        if not self.MUTE:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(self.s_level)

    def gameover(self):
        if not self.MUTE:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(self._make_gameover())

    def _make_gameover(self):
        seg = [sine(mtof(72), 250, 0.5), sine(mtof(68), 300, 0.5), sine(mtof(63), 600, 0.5)]
        gap = np.zeros(int(SR * 0.05))
        w = np.concatenate([seg[0], gap, seg[1], gap, seg[2]])
        return to_sound(w)

    def stop(self):
        self._running = False
