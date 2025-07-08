# ========= main.py =========
"""
30‑second countdown (with overlay)  ➜  10‑second sting video  ➜  loop
Streams to an RTMPS endpoint with a single, persistent FFmpeg process.
"""

import argparse
import sys
import time
from pathlib import Path
from threading import Thread

import cv2
import numpy as np
import subprocess as sp

import config as cfg   # make sure config.py sits next to this script


# ---------- helpers ----------------------------------------------------------


def _verify_paths() -> None:
    """Exit early if any required asset is missing."""
    required = [cfg.BACKGROUND_VIDEO, cfg.FINAL_VIDEO]
    missing = [p for p in required if not Path(p).exists()]
    if missing:
        for p in missing:
            print(f"[ERROR] Missing file: {p}", file=sys.stderr)
        sys.exit(1)


def draw_centered_countdown(frame: np.ndarray, secs_left: int) -> np.ndarray:
    """Returns frame with big white mm:ss text in the centre."""
    h, w = frame.shape[:2]
    mm, ss = divmod(secs_left, 60)
    text = f"{mm:02}:{ss:02}"

    scale = h / 720 * 2.6
    thick = max(2, int(h / 720 * 3))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)

    x = (w - tw) // 2
    y = (h + th) // 2
    pad = int(h * 0.02)

    cv2.rectangle(frame,
                  (x - pad, y - th - pad),
                  (x + tw + pad, y + pad),
                  (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255, 255, 255), thick, cv2.LINE_AA)
    return frame


def resize_letterbox(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Keeps aspect ratio, adds black bars if needed (letter‑box)."""
    h, w = frame.shape[:2]
    tgt_ar, src_ar = target_w / target_h, w / h

    if src_ar > tgt_ar:                      # fit to width
        new_w = target_w
        new_h = int(h * target_w / w)
        frame = cv2.resize(frame, (new_w, new_h))
        pad = (target_h - new_h) // 2
        frame = cv2.copyMakeBorder(frame, pad, target_h - new_h - pad, 0, 0,
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
    else:                                    # fit to height
        new_h = target_h
        new_w = int(w * target_h / h)
        frame = cv2.resize(frame, (new_w, new_h))
        pad = (target_w - new_w) // 2
        frame = cv2.copyMakeBorder(frame, 0, 0, pad, target_w - new_w - pad,
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return frame


# ---------- frame generator --------------------------------------------------


def countdown_and_final_frames(cycle_secs: int):
    """
    Infinite generator:

        1. Plays BACKGROUND_VIDEO in a loop and overlays countdown.
        2. When 10 s remain, switches to frames from FINAL_VIDEO once.
        3. Starts over forever.

    Yields raw BGR frames sized to cfg.RESOLUTION.
    """
    tgt_w, tgt_h = cfg.RESOLUTION

    while True:
        # -- 1) countdown phase --
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

        # -- 2) final‑sting phase (10 s, play once) --
        fin_cap = cv2.VideoCapture(str(cfg.FINAL_VIDEO))
        while True:
            ok, frame = fin_cap.read()
            if not ok:
                break
            frame = resize_letterbox(frame, tgt_w, tgt_h)
            yield frame
        fin_cap.release()
        # loop restarts automatically


# ---------- streaming loop ---------------------------------------------------


def _start_ffmpeg() -> sp.Popen:
    """Launches one FFmpeg process that stays up and takes raw frames through stdin."""
    w, h = cfg.RESOLUTION
    cmd = [
        "ffmpeg",
        "-loglevel", "error",

        # ---------- video from Python ----------
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}",
        "-r", str(cfg.FPS),
        "-i", "-",                          # stdin

        # ---------- audio bed (looped) ----------
        "-stream_loop", "-1",
        "-i", str(cfg.BACKGROUND_VIDEO),    # re‑using the video file just for audio!

        # ---------- mapping ----------
        "-map", "0:v:0",
        "-map", "1:a:0",

        # ---------- encoding ----------
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", cfg.VIDEO_BITRATE,
        "-pix_fmt", "yuv420p",

        "-c:a", "aac",
        "-b:a", cfg.AUDIO_BITRATE,

        "-f", "flv",
        cfg.RTMP_URL,
    ]
    return sp.Popen(cmd, stdin=sp.PIPE, bufsize=10_485_760)   # 10 MB buffer


def run_stream():
    """Main endless streaming loop; auto‑restarts FFmpeg if the link dies."""
    print("[Stream] Connecting to RTMP… (Ctrl‑C to quit)")
    retry_delay = 5

    while True:
        ffmpeg = _start_ffmpeg()
        print("[Stream] ➜ live")

        try:
            for frame in countdown_and_final_frames(cfg.COUNTDOWN_SECONDS):
                try:
                    ffmpeg.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    raise RuntimeError("FFmpeg pipe closed")
        except KeyboardInterrupt:
            print("\n[Stream] ⬛ Stopping by user…")
            ffmpeg.stdin.close()
            ffmpeg.terminate()
            break
        except Exception as e:
            # connection likely dropped
            print(f"[Warn] {e}. Re‑connecting in {retry_delay}s…")
            try:
                ffmpeg.stdin.close()
            except Exception:
                pass
            ffmpeg.terminate()
            time.sleep(retry_delay)
            continue


# ---------- preview (local window) -------------------------------------------


def run_preview():
    """Simple local preview window; press 'q' to exit."""
    win = cfg.WINDOW_TITLE
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, *cfg.RESOLUTION)

    for frame in countdown_and_final_frames(cfg.COUNTDOWN_SECONDS):
        cv2.imshow(win, frame)
        if cv2.waitKey(int(1_000 / cfg.FPS)) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()


# ---------- main entry -------------------------------------------------------


if __name__ == "__main__":
    _verify_paths()

    parser = argparse.ArgumentParser(description="Looping countdown streamer")
    parser.add_argument("--mode", choices=("preview", "stream"), default="preview")
    args = parser.parse_args()

    if args.mode == "preview":
         run_stream()
       
    else:
        run_preview()
