# Tapo Monitor

Sistema de monitorización de ruido y captura de imagen mediante cámara Tapo C211.

## Características

- Lectura de audio vía FFmpeg sobre RTSP.
- Cálculo de picos PCM, dBFS y estimación aproximada de dB SPL.
- Captura de frames de vídeo con OpenCV.
- Envío de notificaciones a NTFY con imagen adjunta.
- Auto-reconexión de streams.

## Estructura del proyecto

```
/
 ├── tapo.py
 ├── requirements.txt
 ├── README.md
 └── .env        (debes crearlo tú)
```

---

# Archivo `.env`

El archivo `.env` debe crearse manualmente con estas variables. Incluyo uno de ejemplo:

```env
RTSP_VIDEO=rtsp://usuario:password@IP:554/stream1/main  # Endpoint RTSP de vídeo
RTSP_AUDIO=rtsp://usuario:password@IP:554/stream2       # Endpoint RTSP de audio

# Endpoints y creds para topic NTFY
NTFY_URL=https://ntfy.tu-servidor.com/tapo_notifications
NTFY_USER=tu_usuario
NTFY_PASSWORD=tu_password

SOUND_THRESHOLD=-25                  # Umbral de sonido. Cuanto más cerca de 0, más sensible. Hace referencia a dBFS
COOLDOWN=5                           # Tiempo mínimo entre alertas
AUDIO_CHUNK_SECONDS=0.1              # Duración de cada bloque de audio que analiza FFmpeg, en segundos

DEBUG_AUDIO=false                    # Modo debug del audio
```

---

# Ejecución local

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Ejecutar:

```bash
python tapo.py
```

---

# Notas importantes

- NTFY debe estar disponible.
- Debes indicar que los RTSP son funcionales.
