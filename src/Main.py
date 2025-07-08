# ========= main.py =========
"""
Live Stream: 30‑second countdown ➜ 10‑second sting ➜ loop
Streams to RTMP using FFmpeg. Ready for GitHub Actions.
"""

import sys
import time
import subprocess as sp
from pathlib import Path

import cv2
import numpy as np
import config as cfg


# ───── Path Check ─────
def _verify_paths():
    required = [cfg.BACKGROUND_VIDEO, cfg.FINAL_VIDEO]
    for p in required:
        if not Path(p).exists():
            print(f"[ERROR] Missing file: {p}", file=sys.stderr)
            sys.exit(1)


# ───── Frame Utils ─────
def draw_centered_countdown(frame: np.ndarray, secs_left: int) -> np.ndarray:
    h, w = frame.shape[:2]
    mm, ss = divmod(secs_left, 60)
    text = f"{mm:02}:{ss:02}"

    scale = h / 720 * 2.6
    thick = max(2, int(h / 720 * 3))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)

    x = (w - tw) // 2
    y = (h + th) // 2
    pad = int(h * 0.02)

    cv2.rectangle(frame, (x - pad, y - th - pad), (x + tw + pad, y + pad), (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), thick, cv2.LINE_AA)
    return frame


def resize_letterbox(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    h, w = frame.shape[:2]
    tgt_ar, src_ar = target_w / target_h, w / h

    if src_ar > tgt_ar:
        new_w = target_w
        new_h = int(h * target_w / w)
        frame = cv2.resize(frame, (new_w, new_h))
        pad = (target_h - new_h) // 2
        frame = cv2.copyMakeBorder(frame, pad, target_h - new_h - pad, 0, 0,
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
    else:
        new_h = target_h
        new_w = int(w * target_h / h)
        frame = cv2.resize(frame, (new_w, new_h))
        pad = (target_w - new_w) // 2
        frame = cv2.copyMakeBorder(frame, 0, 0, pad, target_w - new_w - pad,
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return frame


# ───── Frame Generator ─────
def countdown_and_final_frames(cycle_secs: int):
    tgt_w, tgt_h = cfg.RESOLUTION

    while True:
        # Countdown video loop
        bg_cap = cv2.VideoCapture(str(cfg.BACKGROUND_VIDEO))
        start_ts = time.time()

        while True:
            ok, frame = bg_cap.read()
            if not ok:
                bg_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            elapsed = int(time.time() - start_ts)
            left = cycle_secs - elapsed
            frame = resize_letterbox(frame, tgt_w, tgt_h)
            frame = draw_centered_countdown(frame, left)
            yield frame

            if left <= 10:
                break

        bg_cap.release()

        # Final sting video once
        fin_cap = cv2.VideoCapture(str(cfg.FINAL_VIDEO))
        while True:
            ok, frame = fin_cap.read()
            if not ok:
                break
            frame = resize_letterbox(frame, tgt_w, tgt_h)
            yield frame
        fin_cap.release()


# ───── FFmpeg Stream ─────
def _start_ffmpeg() -> sp.Popen:
    w, h = cfg.RESOLUTION
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}",
        "-r", str(cfg.FPS),
        "-i", "-",
        "-stream_loop", "-1",
        "-i", str(cfg.BACKGROUND_VIDEO),  # for audio
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", cfg.VIDEO_BITRATE,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", cfg.AUDIO_BITRATE,
        "-f", "flv",
        cfg.RTMP_URL,
    ]
    return sp.Popen(cmd, stdin=sp.PIPE, bufsize=10_485_760)


# ───── Main Stream Loop ─────
def run_stream():
    print("[Stream] Connecting to RTMP…")
    retry_delay = 5

    while True:
        ffmpeg = _start_ffmpeg()
        print("[Stream] ➜ live")

        try:
            for frame in countdown_and_final_frames(cfg.COUNTDOWN_SECONDS):
                ffmpeg.stdin.write(frame.tobytes())
        except Exception as e:
            print(f"[Warn] {e}. Reconnecting in {retry_delay}s…")
            try:
                ffmpeg.stdin.close()
            except:
                pass
            ffmpeg.terminate()
            time.sleep(retry_delay)
            continue


# ───── Entry Point ─────
if __name__ == "__main__":
    _verify_paths()
    run_stream()  # Force stream mode only (no preview)
