import os
import cv2
import numpy as np
import requests
import datetime
import time
import subprocess
import logging
import math

# ---------------------------------------------------------

RTSP_VIDEO = os.getenv("RTSP_VIDEO")
RTSP_AUDIO = os.getenv("RTSP_AUDIO")
NTFY_URL = os.getenv("NTFY_URL")
NTFY_USER = os.getenv("NTFY_USER")
NTFY_PASSWORD = os.getenv("NTFY_PASSWORD")
SOUND_THRESHOLD = float(os.getenv("SOUND_THRESHOLD"))
COOLDOWN = int(os.getenv("COOLDOWN"))
AUDIO_CHUNK_SECONDS = float(os.getenv("AUDIO_CHUNK_SECONDS"))
DEBUG_AUDIO = os.getenv("DEBUG_AUDIO").lower() == "true"

AUDIO_CHUNK_BYTES = int(16000 * 2 * AUDIO_CHUNK_SECONDS)

required_vars = [
    ("RTSP_VIDEO", RTSP_VIDEO),
    ("RTSP_AUDIO", RTSP_AUDIO),
    ("NTFY_URL", NTFY_URL),
    ("NTFY_USER", NTFY_USER),
    ("NTFY_PASSWORD", NTFY_PASSWORD),
    ("SOUND_THRESHOLD", SOUND_THRESHOLD),
    ("COOLDOWN", COOLDOWN),
    ("AUDIO_CHUNK_SECONDS", AUDIO_CHUNK_SECONDS),
    ("DEBUG_AUDIO", DEBUG_AUDIO),
]

missing = [name for name, value in required_vars if value is None]
if missing:
    raise RuntimeError(f"FALTAN variables en .env: {missing}")

# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------------------------------------------------
# Conversión PCM → dBFS
# ---------------------------------------------------------
def pcm_to_dbfs(value):
    return 20 * math.log10(value / 32767.0) if value > 0 else -120.0

# ---------------------------------------------------------
# NTFY
# ---------------------------------------------------------
def send_ntfy(title, body="", file_bytes=None, tags=None):
    logging.info(f"Enviando alerta a ntfy: {title}")
    headers = {
        "Title": title,
        "Priority": "high"
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    try:
        if file_bytes:
            try:
                requests.post(
                    NTFY_URL,
                    headers=headers,
                    data=body.encode("utf-8"),
                    auth=(NTFY_USER, NTFY_PASSWORD),
                    timeout=6
                )
            except Exception as e:
                logging.error(f"Error enviando texto a ntfy: {e}")

            try:
                file_headers = headers.copy()
                file_headers["Content-Type"] = "image/jpeg"
                requests.post(
                    NTFY_URL,
                    headers=file_headers,
                    data=file_bytes,
                    auth=(NTFY_USER, NTFY_PASSWORD),
                    timeout=10
                )
            except Exception as e:
                logging.error(f"Error enviando adjunto a ntfy: {e}")

        else:
            requests.post(
                NTFY_URL,
                headers=headers,
                data=body.encode("utf-8"),
                auth=(NTFY_USER, NTFY_PASSWORD),
                timeout=6
            )

    except Exception as e:
        logging.error(f"Error enviando ntfy: {e}")

# ---------------------------------------------------------
# AUDIO via FFmpeg
# ---------------------------------------------------------
logging.info("Iniciando monitorización…")
logging.info(f"Audio (stream2): {RTSP_AUDIO}")
logging.info(f"Vídeo (stream1): {RTSP_VIDEO}")

RECONNECT_DELTA_SECONDS = 3.0
RECONNECT_INTERVAL = 600.0

def start_audio_process():
    return subprocess.Popen([
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-analyzeduration", "0",
        "-probesize", "32",
        "-i", RTSP_AUDIO,
        "-vn",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-loglevel", "quiet",
        "-"
    ], stdout=subprocess.PIPE)

def start_video_capture():
    cap_local = cv2.VideoCapture(RTSP_VIDEO)
    time.sleep(1)
    return cap_local

ffmpeg_audio = start_audio_process()
logging.info("Audio conectado correctamente @ stream2.")

last_restart_time = time.time()

def restart_streams():
    global ffmpeg_audio, cap, last_restart_time, last_frame, last_frame_ts
    logging.info("Reiniciando streams (reconnect)…")
    try:
        if ffmpeg_audio and ffmpeg_audio.poll() is None:
            ffmpeg_audio.kill()
    except:
        pass

    try:
        cap.release()
    except:
        pass

    time.sleep(0.5)

    ffmpeg_audio = start_audio_process()
    cap = start_video_capture()

    try:
        r, f = cap.read()
        if r and f is not None:
            last_frame = f.copy()
            last_frame_ts = datetime.datetime.now()
    except:
        pass

    last_restart_time = time.time()

# ---------------------------------------------------------
# VÍDEO via OpenCV
# ---------------------------------------------------------
cap = cv2.VideoCapture(RTSP_VIDEO)
time.sleep(1)

ret, frame = cap.read()
if not ret or frame is None:
    logging.error("[ERROR] No se pudo abrir el stream de vídeo.")
    exit(1)

height, width = frame.shape[:2]
logging.info(f"Vídeo conectado: {width}x{height}")

send_ntfy(
    "Monitor Tapo C211",
    "Servicio activo",
    tags=["white_check_mark"]
)

last_alert = 0
last_frame_ts = datetime.datetime.now()
FLUSH_MAX_SECONDS = 1.0

# ---------------------------------------------------------
# LOOP PRINCIPAL
# ---------------------------------------------------------
while True:

    # ------------------ VIDEO ------------------
    ret, frame = cap.read()
    if ret and frame is not None:
        try:
            last_frame = frame.copy()
        except:
            last_frame = frame
    else:
        logging.warning("[ERROR] Vídeo perdido, reconectando…")
        cap.release()
        time.sleep(1)
        cap = cv2.VideoCapture(RTSP_VIDEO)
        continue

    # ------------------ AUDIO ------------------
    raw = ffmpeg_audio.stdout.read(AUDIO_CHUNK_BYTES)

    if raw:
        audio = np.frombuffer(raw, dtype=np.int16)
        peak_pcm = int(np.max(np.abs(audio))) if audio.size > 0 else 0
        peak_db = pcm_to_dbfs(peak_pcm)

        if audio.size > 0:
            rms = math.sqrt(np.mean(np.square(audio.astype(float))))
            rms_db = pcm_to_dbfs(rms)
        else:
            rms_db = -120.0
            rms = 0

        # ------------------ dB SPL estimado ------------------
        estimated_peak_spl = 90 + peak_db
        estimated_rms_spl = 90 + rms_db

        if DEBUG_AUDIO:
            logging.info(
                f"[AUDIO DEBUG] chunk={len(raw)} | peak PCM={peak_pcm} | "
                f"peak dB SPL={estimated_peak_spl:.1f} | "
                f"min={audio.min() if audio.size else 'x'} | "
                f"max={audio.max() if audio.size else 'x'}"
            )

    else:
        peak_db = -120.0
        rms_db = -120.0
        peak_pcm = 0
        rms = 0
        estimated_peak_spl = 0
        estimated_rms_spl = 0

    bark_detected = peak_db > SOUND_THRESHOLD
    now = time.time()

    if not bark_detected or (now - last_alert < COOLDOWN):
        time.sleep(0.01)
        continue

    logging.info(f"🔊 Ruido detectado ({peak_db:.1f} dBFS, {estimated_peak_spl:.1f} dB SPL)")

    # ------------------ CAPTURA DE FOTO ------------------
    end_flush = time.time() + FLUSH_MAX_SECONDS
    try:
        while time.time() < end_flush:
            r2, f2 = cap.read()
            if r2 and f2 is not None:
                try:
                    last_frame = f2.copy()
                except:
                    last_frame = f2
                last_frame_ts = datetime.datetime.now()
    except:
        pass

    detection_dt = datetime.datetime.now()
    detection_ts_str = detection_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    delta = None
    frame_ts_str = "unknown"
    if last_frame_ts is not None:
        delta = (detection_dt - last_frame_ts).total_seconds()
        frame_ts_str = last_frame_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        logging.info(f"Delta detección->frame: {delta:.3f}s")

    now_time = time.time()
    if (delta is None) or (delta > RECONNECT_DELTA_SECONDS) or (now_time - last_restart_time > RECONNECT_INTERVAL):
        logging.info("Delta alto — reiniciando streams…")
        restart_streams()

    if last_frame is not None:
        _, jpg = cv2.imencode(".jpg", last_frame)

        if delta is not None:
            body = (
                f"Detección vs Captura: {detection_ts_str} — Delta: {delta:.3f}s\n\n"
                f"Audio:\n"
                f"• Valor PCM: {peak_pcm}\n"
                f"• Volumen: {estimated_peak_spl:.1f} dB (SPL)\n"
            )
        else:
            body = (
                f"Detección vs Captura: {detection_ts_str} — Delta: {delta:.3f}s\n\n"
                f"Audio:\n"
                f"• Valor PCM: {peak_pcm}\n"
                f"• Volumen: {estimated_peak_spl:.1f} dB (SPL)\n"
            )

        send_ntfy(
            "Ruido detectado",
            body,
            file_bytes=jpg.tobytes(),
            tags=["sound"]
        )

    last_alert = now
    time.sleep(0.05)
