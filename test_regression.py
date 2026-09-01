"""Regression suite for SYNTHESIS (headless, no audio/save writes).
Run: python test_regression.py   (exit 0 = all pass)
Checks: syntax, boot, start_game, levelup open/select/choose, empty-pool
auto-resolve, prereq gating, save round-trip, item magnet pull (stray-orb fix),
shard drift, and win/unlock flow. Does NOT touch save.json.
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ast
import tempfile
import time

import numpy as np

import game as G
import game_defs
from game_defs import WORLDS, ITEM_TYPES, xp_next, PULSE_MAX_R

G.HEADLESS = True
G.game_defs.HEADLESS = True


def fresh_game(world=0):
    g = G.Game()
    g.meta.save_enabled = False
    g.meta.world = world
    g.start_game()
    return g


def main():
    results = []

    def check(name, cond, extra=""):
        results.append((name, cond, extra))
        print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))

    # --- syntax ---
    for f in ("game.py", "game_defs.py", "game_entities.py", "game_audio.py"):
        try:
            ast.parse(open(f, encoding="utf-8").read())
            check(f"syntax {f}", True)
        except SyntaxError as e:
            check(f"syntax {f}", False, str(e))

    # --- boot + start ---
    g = fresh_game(0)
    check("boot to menu", True)
    check("arena set", g.arena == WORLDS[0]["arena"], str(g.arena))
    g.update(0.016)
    g.draw()

    # --- levelup open/select/choose ---
    g.open_levelup()
    check("levelup state", g.state == "levelup")
    check("3 options", len(g.levelup_options) == 3, str(len(g.levelup_options)))
    n0 = g.levelup_options[0]["id"]
    g.choose_upgrade(0)
    check("choose applied", g.run_upgrades[n0] == 1)
    check("back to playing", g.state == "playing")

    # --- empty pool auto-resolve ---
    g2 = fresh_game(0)
    g2.run_upgrades = {uid: u["max"] for uid, u in zip(G.UPG_IDS, G.UPG_POOL) for uid in [uid]}
    g2.levelups += 1
    g2.open_levelup()
    check("empty pool stays playing", g2.state == "playing")

    # --- prereq + tier gating ---
    m = g.meta
    core_dmg = next(d for d in game_defs.Meta.DEFS if d["id"] == "core_dmg")
    check("tier2 locked at worlds=0", m.tier_locked(core_dmg))
    m.worlds = 1
    check("tier2 unlocked at worlds=1", not m.tier_locked(core_dmg))
    m.worlds = 0
    check("prereq unmet", not m.prereq_met(core_dmg))

    # --- save round-trip ---
    tmp = tempfile.mktemp(suffix=".json")
    m.save_enabled = True
    m.path = tmp
    m.resonance = 1234
    m.levels["field_xp"] = 2
    m.save()
    m2 = game_defs.Meta(path=tmp)
    check("save round-trip resonance", m2.resonance == 1234)
    check("save round-trip upgrades", m2.levels["field_xp"] == 2)
    try:
        os.remove(tmp)
    except OSError:
        pass

    # --- stray orb fix: item magnet pull ---
    g3 = fresh_game(0)
    start = g3.player.pos.copy()
    g3.items = [G.Item(start + __import__("numpy").array([150.0, 0.0]), "xp", ITEM_TYPES[0])]
    for _ in range(240):
        g3.update(0.016)
    if g3.items:
        d = __import__("math").hypot(g3.items[0].pos[0] - g3.player.pos[0],
                                     g3.items[0].pos[1] - g3.player.pos[1])
        check("item magnet pulls in", d < 140, f"dist={d:.1f}")
    else:
        check("item magnet pulls in", True, "collected")

    # --- shard drift: stray orb shard ---
    g4 = fresh_game(0)
    import math as _m
    import numpy as _np
    sh = G.Shard(_np.array([500.0, 500.0]))
    g4.player.pos = _np.array([100.0, 100.0])
    g4.shards = [sh]
    for _ in range(300):
        g4.update(0.016)
    moved = _m.hypot(sh.pos[0] - 500, sh.pos[1] - 500)
    check("shard drift toward player", moved > 60, f"moved={moved:.1f}")

    # --- 1-hit-to-1-life fix: contact costs exactly one life (invuln window) ---
    g4b = fresh_game(0)
    g4b.player.fire_timer = 999.0
    g4b.enemies = [G.Enemy("chaser", list(g4b.player.pos + _np.array([1.0, 0.0])), 0, 100, (255, 90, 220))]
    before = g4b.lives
    for _ in range(10):
        g4b.update(0.016)
    check("contact costs one life", g4b.lives == before - 1,
          f"lives {before}->{g4b.lives} state={g4b.state}")
    check("not one-hit-killed", g4b.state == "playing")

    # --- win/unlock flow ---
    g5 = fresh_game(2)
    g5.boss = G.Boss([400, 300], 50, (200, 160, 255))
    g5.boss.hp = 5
    for _ in range(2400):
        if g5.state == "levelup":
            g5.choose_upgrade(g5.levelup_sel)
        g5.update(0.016)
        if g5.boss is None:
            break
    check("win state", g5.win, f"state={g5.state} win={g5.win}")
    check("world unlock", g5.meta.worlds >= 3, f"worlds={g5.meta.worlds}")
    check("essence granted", g5.essence_earned > 0, f"essence={g5.essence_earned}")

    # --- pulse glow cap (freeze fix: no giant SRCALPHA surfaces) ---
    g6 = fresh_game(4)
    g6.pulses = [{"pos": np.array([g6.arena[0] / 2, g6.arena[1] / 2]), "r": float(PULSE_MAX_R), "warn": 0.0}]
    _t0 = time.perf_counter()
    g6.draw()
    _dt = time.perf_counter() - _t0
    check("pulse glow draw fast", _dt < 0.1, f"dt={_dt * 1000:.1f}ms")

    # --- xp curve sanity ---
    check("xp_next(1)=10", xp_next(1) == 10)
    check("xp_next(20)=2786", xp_next(20) == 2786)

    # --- save.json untouched ---
    check("save.json untouched", not os.path.exists(G.game_defs.SAVE_PATH))

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n{passed}/{len(results)} checks passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
