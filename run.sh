#!/usr/bin/env bash
# SYNTHESIS launcher - uses bundled venv, no system Python needed
cd "$(dirname "$0")"
PYTHON=".venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "[ERROR] venv not found. Recreate it with:"
    echo "    python3 -m venv .venv"
    echo "    .venv/bin/pip install numpy pygame"
    exit 1
fi
# Fall back to a display server if DISPLAY is unset (WSL2/WXIg)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
# Use the PulseAudio backend in WSL (SDL otherwise falls back to broken "dsp")
export SDL_AUDIODRIVER=pulseaudio
exec "$PYTHON" game.py