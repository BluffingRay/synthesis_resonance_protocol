"""Fast headless balance + drift checks for SYNTHESIS (no rendering).
Usage:
    python sim_balance.py            # balance battery, no audio (fast)
    python sim_balance.py --drift    # 15s real-audio beat drift check
    python sim_balance.py --fast     # tiny battery (1 fresh / 1 veteran / 1 idle)
"""
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import game as G

VETERAN_LEVELS = {"core_frate": 5, "core_dmg": 5, "core_multishot": 3, "aegis_lives": 3,
                  "aegis_shield": 3, "field_magnet": 5, "field_charge": 4, "field_xp": 4,
                  "field_combo": 3, "velocity": 3, "core_pspeed": 4}


def sim_run(g, strategy="smart", max_time=45.0, dt=1 / 30.0, world=0):
    g.state = "playing"
    g.meta.world = world
    g.reset()
    aw, ah = g.arena
    stats = {"time": 0.0, "wave": 0, "score": 0, "level": 0, "upgrades": 0, "win": False}
    it = 0
    while g.state != "over" and stats["time"] < max_time:
        it += 1
        if it > 200000:
            stats["capped"] = True
            break
        if g.state == "levelup" or g.levelups > 0:
            if not g.levelup_options:
                stats["capped"] = "empty-options"
                break
            g.choose_upgrade(g.levelup_sel)
            continue
        p = g.player
        if strategy != "idle":
            near, nd = None, 1e18
            import math
            for e in g.enemies:
                d = math.hypot(e.pos[0] - p.pos[0], e.pos[1] - p.pos[1])
                if d < nd:
                    nd, near = d, e
            if near is not None:
                if nd < 160:
                    away = p.pos - near.pos
                    n2 = math.hypot(away[0], away[1])
                    if n2 < 1:
                        away = np.array([1.0, 0.0])
                    else:
                        away = away / n2
                    p.pos += away * 360 * dt
                else:
                    to_c = np.array([aw / 2, ah / 2]) - p.pos
                    if math.hypot(to_c[0], to_c[1]) > 120:
                        p.pos += to_c / math.hypot(to_c[0], to_c[1]) * 180 * dt
            p.pos[0] = np.clip(p.pos[0], p.radius, aw - p.radius)
            p.pos[1] = np.clip(p.pos[1], p.radius, ah - p.radius)
        g.update(dt)
        stats["time"] += dt
        stats["wave"] = max(stats["wave"], g.wave)
        stats["score"] = g.score
        stats["level"] = max(stats["level"], g.level)
        stats["upgrades"] = sum(g.run_upgrades.values())
        stats["win"] = g.win
    return stats


def run_one(job):
    name, meta_levels, strategy, max_time, world = job
    G.HEADLESS = True
    G.game_defs.HEADLESS = True
    g = G.Game()
    g.meta.save_enabled = False
    if meta_levels:
        for uid, lv in meta_levels.items():
            g.meta.levels[uid] = lv
        g.recompute_stats()
    s = sim_run(g, strategy, max_time, world=world)
    return name, strategy, world, s


def main():
    args = sys.argv[1:]
    if "--drift" in args:
        import pygame
        pygame.mixer.pre_init(G.SR, -16, 2, 512)
        pygame.mixer.init()
        g = G.Game()
        print(f"mixer init OK, MUTE={g.audio.MUTE}; boot state={g.state}")
        t0 = time.perf_counter()
        s0 = g.audio._step
        time.sleep(15)
        elapsed = time.perf_counter() - t0
        gained = g.audio._step - s0
        expected = elapsed / g.audio.STEP
        print(f"beat drift: {gained} steps vs ~{expected:.0f} in {elapsed:.1f}s "
              f"({abs(expected - gained) / expected * 100:.2f}%)")
        g.audio.stop()
        pygame.quit()
        return

    G.HEADLESS = True
    G.game_defs.HEADLESS = True
    jobs = [
        ("fresh", None, "smart", 45.0, 0), ("fresh", None, "smart", 45.0, 0),
        ("fresh", None, "smart", 45.0, 0), ("veteran", VETERAN_LEVELS, "smart", 45.0, 0),
        ("veteran", VETERAN_LEVELS, "smart", 45.0, 0), ("idle", None, "idle", 45.0, 0),
        ("idle", None, "idle", 45.0, 0),
        ("fresh", None, "smart", 45.0, 1), ("veteran", VETERAN_LEVELS, "smart", 45.0, 1),
        ("idle", None, "idle", 45.0, 1),
        ("fresh", None, "smart", 45.0, 2), ("veteran", VETERAN_LEVELS, "smart", 45.0, 2),
        ("idle", None, "idle", 45.0, 2),
        ("fresh", None, "smart", 45.0, 3), ("fresh", None, "smart", 45.0, 3),
        ("idle", None, "idle", 45.0, 3),
        ("veteran", VETERAN_LEVELS, "smart", 120.0, 3),
        ("veteran", VETERAN_LEVELS, "smart", 120.0, 3),
        ("fresh", None, "smart", 45.0, 4), ("fresh", None, "smart", 45.0, 4),
        ("idle", None, "idle", 45.0, 4),
        ("veteran", VETERAN_LEVELS, "smart", 120.0, 4),
        ("veteran", VETERAN_LEVELS, "smart", 120.0, 4),
        ("fresh", None, "smart", 45.0, 5), ("veteran", VETERAN_LEVELS, "smart", 45.0, 5),
        ("idle", None, "idle", 45.0, 5),
    ]
    if "--fast" in args:
        jobs = [("fresh", None, "smart", 30.0, 0), ("veteran", VETERAN_LEVELS, "smart", 30.0, 0),
                ("idle", None, "idle", 30.0, 0),
                ("fresh", None, "smart", 30.0, 3), ("fresh", None, "smart", 30.0, 4)]

    t0 = time.perf_counter()
    if "--serial" in args:
        results = [run_one(j) for j in jobs]
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            results = list(ex.map(run_one, jobs))
    wall = time.perf_counter() - t0

    import statistics as st
    by = {}
    for name, strategy, world, s in results:
        by.setdefault((world, name), []).append(s)
    for w in sorted({w for w, _ in by}):
        wl = G.WORLDS[w]
        boss_wave = wl["waves"]
        print(f"world {w} {wl['name']} ({boss_wave or 'endless'}w):")
        for name in ("fresh", "veteran", "idle"):
            key = (w, name)
            if key not in by:
                continue
            if name == "idle":
                for s in by[key]:
                    print(f"idle:  {s['time']:5.1f}s wave {s['wave']:2d} score {s['score']:6d}")
            else:
                for i, s in enumerate(by[key]):
                    print(f"{name[:5]} run {i+1}: {s['time']:5.1f}s wave {s['wave']:2d} "
                          f"score {s['score']:6d} lvl {s['level']:2d} upg {s['upgrades']:2d}")
                boss_line = ""
                if boss_wave and name == "veteran":
                    kills = sum(1 for s in by[key] if s["win"])
                    boss_line = f" boss {kills}/{len(by[key])}"
                print(f"{name[:5]} avg: wave {st.mean(s['wave'] for s in by[key]):.1f} "
                      f"score {st.mean(s['score'] for s in by[key]):.0f}{boss_line}")
    print(f"wall: {wall:.2f}s (parallel on {os.cpu_count()} cores)" if "--serial" not in args
          else f"wall: {wall:.2f}s (serial)")


if __name__ == "__main__":
    main()
