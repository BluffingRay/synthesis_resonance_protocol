# SYNTHESIS: Resonance Protocol — Project Brief

Read this before working in this project. It is the single source of truth for
context, commands, and conventions shared by all agents.

## What this is

A pygame roguelite (Python 3.13.14, pygame 2.6.1, numpy 2.5.1). Procedural audio,
no art assets. Authoritative project root (WSL): `/home/raymar/SYNTHESIS`. The old
Windows tree `C:\Users\Admin\Desktop\SYNTHESIS` is STALE — do not edit both. WSL runs
with WSLg for video/audio; to enable audio run `sudo apt-get install -y libpulse0`
once and launch via `run.sh` (it exports `SDL_AUDIODRIVER=pulseaudio`).

## Module map

| File | Role |
|---|---|
| `game_defs.py` | Constants (W/H/FPS, colors), `WORLDS`, `BOSS_HP`, wind/bolt/item constants, `ITEM_TYPES`, `Meta` (tech tree + save), `UPG_POOL`, `xp_next`, `wrap` |
| `game_entities.py` | `Starfield`, `Glow`, `Player`, `Projectile`, `Enemy`, `Shard`, `Boss`, `Item` |
| `game.py` | Orchestrator: states, update/draw, camera, gimmicks, boss, items, win/economy, main loop |
| `game_audio.py` | Audio synthesis + `AudioEngine` (reads `game_defs.HEADLESS`) |
| `sim_balance.py` | Headless balance battery (fresh/veteran/idle), parallel on 12 cores |
| `run.bat` | Launcher (Windows) |
| `run.sh` | Launcher (WSL/Linux; exports `SDL_AUDIODRIVER=pulseaudio`) |
| `save.json` | Meta save — **treat as user data, never clobber** |

`game_part1..4.py` were pre-refactor snapshots and are DELETED. Do not recreate.

## Commands

Run from `/home/raymar/SYNTHESIS`. Python is `./.venv/bin/python`.

- Syntax: `./.venv/bin/python -c "import ast; [ast.parse(open(f,encoding='utf-8').read()) for f in ('game.py','game_defs.py','game_entities.py','game_audio.py')]; print('syntax OK')"`
- Boot check: `./.venv/bin/python -c "import game_defs; game_defs.HEADLESS = True; import game; g = game.Game(); g.start_game(); g.update(0.016); g.draw()"`
- Regression suite: `./.venv/bin/python test_regression.py`
- Sim battery (fast): `./.venv/bin/python sim_balance.py --fast`
- Sim battery (full, parallel ~6s): `./.venv/bin/python sim_balance.py`
- Headless run template (no audio/window dependency):
  ```python
  import game_defs; game_defs.HEADLESS = True
  import game
  g = game.Game()
  ```

## Conventions

- 4-space indent, double-quoted strings, no comments unless asked.
- **Perf**: never use `np.linalg.norm` — use `math.hypot` (it's ~5x faster and
  the sim profile depends on it). Distance loops are the hot path.
- Keep tuning values in `game_defs.py`; logic in `game.py`.
- Headless tests that end a run call `meta.save()` — set
  `g.meta.save_enabled = False` in tests, or delete `save.json` afterward.

## Current verified balance baselines (re-run before trusting)

XP model: enemy kills grant a flat, kind-based `KILL_XP` (`{"chaser":4,"liner":8,"drifter":12}`, fallback `KILL_XP_DEFAULT=6`) plus `BOSS_XP=2500` on boss kill, scaled by a per-world multiplier `XP_WORLD_MULT=[1.4,1.2,1.2,3.0,4.0,1.5]` (game_defs.py). This is heat-independent — it kills the HP->XP->level->heat positive feedback loop.

Full battery is now per-world; world 0 keeps the legacy distribution (3 fresh /
2 veteran / 2 idle @45s) so old numbers stay comparable. Worlds 1/2 and world 5
CRIMSON (endless) run 1 each @45s; worlds 3/4 (AZURE/OBSIDIAN) run 2 fresh +
1 idle @45s + 2 veteran @120s (to reach+kill the late boss). `--fast` is
1 fresh/veteran/idle @30s on world 0 + 1 fresh @30s on worlds 3/4.

- World 0 NEON CITY (12w): fresh ~8-10, veteran reaches wave 12 / boss 1/1-2/2 @45s, idle ~8.
- World 1 CHROME DESERT (14w): fresh ~8, veteran ~6 (single 45s run swingy — boss reachable ~1/3 on longer runs), idle ~11.
- World 2 VIOLET STORM (16w): fresh ~8-9, veteran ~12-13 (single 45s swingy), idle ~12.
- World 3 AZURE ABYSS (18w): fresh ~6-7, veteran reaches wave 18 / lvl 23-27 (boss reachable+swingy kill @120s), idle ~7.
- World 4 OBSIDIAN SIGNAL (20w): fresh ~6-7, veteran reaches wave 20 / lvl 26-27 (boss reachable; kill swingy @120s), idle ~7-8.
- World 5 CRIMSON PROTOCOL (endless): fresh ~8, veteran ~10, idle ~6.
- `--fast` (30s): world 0 fresh ~6 / vet ~9 / idle ~9, world 3 fresh ~4, world 4 fresh ~4.
- Sim wall time: full ~3-4s, fast ~0.4s (ProcessPoolExecutor, 12 cores; was ~24.7s/2.6s pre-rewrite).
- Idle never clears a world (all bosses/wave totals unreached), so no world is idle-winnable.
- `xp_next` is piecewise (game_defs.py): levels 1–8 keep the classic `10*level**1.65`
  (early progression identical → fresh early power untouched), levels 9+ steepen to
  `xp_next(8)*(level/8)**2.4`, so late/high levels cost ~2x more. Combined with flat KILL_XP,
  veteran late-level cadence lands ~a level every 30-60s (no deluge); levels 1–8 are
  bit-identical, so no early progression is lost.

## Current verified roguelite structure

- 6 worlds: NEON CITY (12w, 1280x720, none), CHROME DESERT (14w, 1440x810,
  sandstorm), VIOLET STORM (16w, 1600x900, storm), AZURE ABYSS (18w, 1920x1080,
  mines), OBSIDIAN SIGNAL (20w, 2080x1170, pulse), CRIMSON PROTOCOL (endless,
  1760x990, overdrive). Worlds 0/1/2/3/4 end with a boss that signals a win
  (BOSS_HP {0:90, 1:150, 2:240, 3:350, 4:480}); world 5 (CRIMSON) is the
  endless finale (no boss). Progression is linear 0→1→2→3→4→5: winning world N
  unlocks world N+1 (the old wave-20 CRIMSON unlock gate is gone).
- sim_balance.py now runs the battery across all 6 worlds; `sim_run` takes a
  `world` index and clamps the player to that world's arena (not screen W/H).
- Arena is per-world and larger than the screen; `game.py` uses `self.cam`
  (world→screen offset). All entity draws take `cam`; UI/HUD draws are
  screen-space and must NOT use cam.
- Gimmicks: sandstorm = wind vectors (player/enemies/shards/items),
  storm = lightning bolts, overdrive = faster fire + more shards/damage.
- Items: xp CACHE (cyan, +xp/shards), OVERDRIVE (orange, buff), MEDKIT (green,
  +life), CORE SURGE (yellow, charge). Items now pull toward the player within
  magnet range like shards.
- Economy: Essence on death AND win (win ~2.5x + world bonus + world unlock).
  Saving via `meta.resonance`.

## Known issues log

| Status | Issue | Root cause / fix |
|---|---|---|
| FIXED | Too much XP after world 1 — level-up on nearly every small movement (constant interruptions, not incremental) | Root cause: HP-scaled kill XP (`maxhp*3`, HP inflates with heat → XP inflates → faster leveling → more heat = positive feedback). Two-part fix: (1) `xp_next` is now piecewise — levels 1–8 keep the classic `10*level**1.65` curve (early/fresh unchanged), levels 9+ steepen to `xp_next(8)*(level/8)**2.4`; (2) kill XP is now FLAT and heat-independent via `KILL_XP`/`KILL_XP_DEFAULT`/`BOSS_XP` + per-world `XP_WORLD_MULT` (see baselines). Veteran late cadence ~a level every 30-60s, no deluge; worlds 3/4 veteran still reach+kill boss. test_regression 27/27. Also deleted a leftover `save.json` polluting `Meta.load()`. |
| FIXED | Stray XP shard at game start | Shards clamped into arena, drift pull (90) outside magnet (160), SHARD_LIFE=9, cap 120 |
| FIXED | "Exp orb" at level start | It was the xp CACHE **item**, which had no player attraction — items now magnet-pull like shards (game_entities `Item.update`) |
| FIXED | Boss fight win path broken (test win state / world unlock failed) | Boss refactor moved `Boss` TWICE per frame (in-branch + shared `pos += vel*dt`) = 2x speed, so legacy boss closed on a stationary player and killed it before shots landed; plus `fire()` never aimed at the boss, so with no minions alive the player shot at `p.pos+p.vel` (zero-velocity duds). Fixed: single move in `Boss.update` (game_entities.py:281/284 removed, shared move once) and `fire()` aims at `self.boss` when no enemies (game.py:151-152). Verified 24/24 x3 and world-3/4 boss win path headless. |
| FIXED | Gameover text on CRIMSON PROTOCOL (world 3, endless) said "THE LAST WORLD IS ENDLESS" | Superseded by the world reorder: CRIMSON is now world 5, the genuinely last world, so "THIS WORLD IS ENDLESS" is now correct. Fix (game.py:1066) stands. |
| FIXED | 1-contact kill in world 0 (enemy touch drained all 3 lives in ~3 frames) | Enemy contact checked every frame with only a 2% knockback (game.py:301-303) and no invulnerability, so a single overlapping enemy re-triggered `damage_player()` each frame and dropped lives 3->2->1->0 in ~50ms. Fix: per-hit invuln window `HIT_INVULN=0.6s` (game_defs.py) — `damage_player()` early-returns while `self.hit_i>0` and sets it on any landed hit (shield or life). One contact now costs exactly one life. Regression checks "contact costs one life" / "not one-hit-killed" added to test_regression.py (27/27). |
| FIXED | Window "Not Responding" / multi-second frame freeze on OBSIDIAN SIGNAL (world 4) | The pulse draw passed the full expanding pulse radius (up to `PULSE_MAX_R`=1200+) to `Glow.circle` (game.py:1151), which builds 3 additive `SRCALPHA` surfaces of `(radius*3.1)^2` px each — a 1250-radius pulse allocated ~450MB/frame and took ~174-194ms/frame (verified), freezing the window. Fixed: defensive cap `GLOW_MAX_RADIUS=120` in `Glow.circle` (game_entities.py) bounds every glow surface; ring outline still renders at full radius (~0.02ms). Pulse draw now flat ~4-8ms at any radius. Regression check "pulse glow draw fast" added to test_regression.py. |
| OPEN | Sim is only as trustworthy as baselines | Re-run battery after any tuning |
| FIXED | Shop / tech-tree vertical navigation was inverted: pressing W/UP moved the cursor DOWN, S/DOWN moved UP. | Root cause: old layout used `shop_pos` y = 490 - row*118 (bigger row = higher on screen) yet `shop_move` matched grid neighbors by (col,row), so key signs inverted. Fixed in the same pass as the tree-layout revamp: `shop_pos` is now RADIAL (hub + 4 branches; tier = distance from center), and `shop_move` is nearest-neighbor in screen coords (UP→smaller y, DOWN→bigger, LEFT→smaller x, RIGHT→bigger). Node data (game_defs Meta.DEFS) unchanged. Verified nav non-inverted headless + visually via vision agent; 27/27. |
| OPEN | CRIMSON PROTOCOL is the hardest fresh world (wave ~6 @45s) | Less relevant now: CRIMSON is world 5, the post-game endless finale reached last, so its fresh difficulty is moot (players arrive with late-game power). Overdrive gimmick is 1.35x enemy count (game.py:645) with no combat offset for the player; consider 1.25x or a player buff. Also mines/pulse/sandstorm make late-world veteran runs swingy (world 3 ~1/3 pre-boss deaths to mines, world 1 boss ~1/3 win rate). Nothing is broken — tune only if intended. |
| FIXED | No audio in WSL ("MUTE: no audio device"); pygame window ran but silent. | SDL fell back to the broken OSS `dsp` driver instead of WSLg's PulseAudio. Fix: `sudo apt-get install -y libpulse0` once, and `run.sh` exports `SDL_AUDIODRIVER=pulseaudio`. Video/display needed no extra setup (WSLg present). |

If you fix a bug, add a row here so the team doesn't rediscover it.
