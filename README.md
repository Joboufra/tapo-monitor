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
tapo/
 ├── tapo.py
 ├── requirements.txt
 ├── README.md
 ├── .env        (debes crearlo tú)
 └── k8s/        (manifiestos y Dockerfile para Kubernetes)
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

Requisitos del sistema:

- FFmpeg instalado y disponible en el PATH (Windows, Linux o macOS).
- Dependencias Python del proyecto.

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Ejecutar:

```bash
python tapo.py
```

---

# Docker Ready

Este proyecto tiene una imagen oficial publicada en Docker Hub:

🔗 **https://hub.docker.com/repository/docker/joboufra/tapo-monitor**

Puedes ejecutarla así:

```bash
docker run --rm   -e RTSP_VIDEO=rtsp://...   -e RTSP_AUDIO=rtsp://...   -e NTFY_URL=https://...   -e NTFY_USER=...   -e NTFY_PASSWORD=...   -e SOUND_THRESHOLD=-25   -e COOLDOWN=5   -e AUDIO_CHUNK_SECONDS=0.1   -e DEBUG_AUDIO=false   joboufra/tapo-monitor:latest
```

O realizar las adaptaciones que consideres para llevar el proyecto a Kubernetes, por ejemplo.

---
# Kubernetes (carpeta `k8s/`)

La carpeta `k8s/` incluye una versión del proyecto preparada para Kubernetes:

- `k8s/Dockerfile` y `k8s/requirements.txt` para construir la imagen.
- `k8s/deployment.yml` con `Deployment`, `ConfigMap` y `Secret`.

Para que funcione en tu clúster necesitas:

- Crear el `Secret` con credenciales reales (RTSP y contraseña NTFY).
- Ajustar el `ConfigMap` con tu URL/usuario de NTFY y parámetros de audio.
- Definir el namespace correcto y la imagen publicada en tu registry.

Nota: no subas credenciales ni endpoints privados al repositorio; usa placeholders o archivos fuera de Git para tus secretos.

---
# Notas importantes
- NTFY debe estar disponible.
- Debes indicar que los RTSP son funcionales.
