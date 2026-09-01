# SYNTHESIS: Resonance Protocol

> **⚠️ This is an EXPERIMENT — not a serious product.**
>
> The whole point of this project is to stress-test how far Agentic AI can take a
> game idea on its own: from sketch to a working procedural roguelite. The code,
> balance, audio, and structure were largely planned and written with agentic
> tooling. Treat it as a tech demo of what that workflow can produce — not as a
> polished, sellable game. It works, though. HAHAHAHA.

A **procedural audiovisual roguelite** built in Python with `pygame`. No art
assets — every visual and every sound is synthesized from math. Survive six
linearly-unlocked worlds, dodge environmental gimmicks, kill a boss to win each
world, and spend **Essence** on a radial tech tree.

## 🖼️ Screenshots

_Add screenshots here! Drop image files into a `screenshots/` folder and
reference them below, e.g.:_

```md
![Neon City](screenshots/neon-city.png)
```

`save.json` is git-ignored user data. The game is best played on a desktop with a
keyboard (there is no mouse / mobile support).

---

## 🧪 The Experiment

This repo exists primarily to answer a question: **how well can Agentic AI build
a complete, balanced, playable game?** The project brief (`AGENTS.md` + the
handoff doc) defined the vision and constraints; subagents planned the architecture,
wrote the modules, tuned the difficulty balance with headless simulations, and
kept a regression suite green. See `AGENTS.md` for the full design rationale,
balance baselines, and known-issue log.

## 🎮 How to Run

Requirements: **Python 3.13+**, `pygame`, `numpy`.

### Windows

```bat
python -m venv venv
venv\Scripts\pip install numpy pygame
run.bat
```

### WSL / Linux

```bash
python3 -m venv .venv
.venv/bin/pip install numpy pygame
# one-time, for audio in WSL:
sudo apt-get install -y libpulse0
export SDL_AUDIODRIVER=pulseaudio
./run.sh
```

(The launchers bundle the venv automatically; `run.bat`/`run.sh` check for it
and print setup instructions if missing.)

### Run from source directly

```bash
python game.py
```

## 📦 Specs

- **Language / stack:** Python 3.13, pygame 2.6, numpy 2.5. Procedural audio, no art assets.
- **Genre:** Top-down procedural roguelite (survivor-style).
- **6 worlds**, linearly unlocked by winning the previous one:
  | World | Waves | Arena | Gimmick |
  |---|---|---|---|
  | 0 NEON CITY | 12 | 1280x720 | none |
  | 1 CHROME DESERT | 14 | 1440x810 | sandstorm (wind) |
  | 2 VIOLET STORM | 16 | 1600x900 | lightning bolts |
  | 3 AZURE ABYSS | 18 | 1920x1080 | mines |
  | 4 OBSIDIAN SIGNAL | 20 | 2080x1170 | expanding pulse |
  | 5 CRIMSON PROTOCOL | endless | 1760x990 | overdrive |

- **Combat:** player projectiles vs. `chaser` / `liner` / `drifter` enemies;
  shards + items (XP cache, overdrive, medkit, core surge) magnet-pull to the player.
- **Progression:** flat, heat-independent kill XP (`KILL_XP`), piecewise `xp_next`
  curve, boss rewards (`BOSS_XP`), world-unlock gating.
- **Meta:** radial hub-and-branch tech tree; **Essence** earned on death and win;
  persistent meta saved to `save.json`.
- **Perf rule:** distance loops use `math.hypot` (not `np.linalg.norm`, ~5x faster).

## 🧪 Tests / Tooling

- `./.venv/bin/python test_regression.py` — regression suite (**27 checks**).
- `./.venv/bin/python sim_balance.py --fast` — headless difficulty battery.
- Headless run (no window/audio):

  ```python
  import game_defs; game_defs.HEADLESS = True
  import game; g = game.Game()
  ```

## 📚 Docs

- `AGENTS.md` — full project brief: module map, commands, balance baselines, known-issue log.
