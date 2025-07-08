"""
All tunables live here so you never have to touch main.py.
"""

import os
from pathlib import Path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- Paths -----------------------------------------------------------

BACKGROUND_VIDEO  = os.path.join(BASE_DIR, 'assets', 'bacground.mp4')
FINAL_VIDEO       = os.path.join(BASE_DIR, 'assets', 'ten.mp4')

# ---------- Countdown -------------------------------------------------------
COUNTDOWN_SECONDS = 30          # 30‑minute show‑open. Change as you wish.
RESOLUTION        = (1280, 720)      # (width, height)
FPS               = 30               # Match the source files
FONT_FILE         = os.path.join(BASE_DIR, 'assets', 'arialbd.ttf')
FONT_SIZE         = 96               # px

# ---------- Streaming -------------------------------------------------------
# Your full RTMP URL, *including* the stream key.  Example:
RTMP_URL          = "rtmps://live-api-s.facebook.com:443/rtmp/FB-705229332491954-0-Ab0-uWMZiS5nWVLw9Fv_LUOo"

VIDEO_BITRATE     = "1000k"
AUDIO_BITRATE     = "96k"

# ---------- Preview window --------------------------------------------------
WINDOW_TITLE      = "⏯  Preview – press ‘q’ to quit"
