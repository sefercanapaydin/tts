# app.py
import os
import math
import random
import time
import uuid
import multiprocessing
import io
from typing import List
from utils_circle import save_circle_with_text_to_images
from PIL import Image
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

APP_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FOLDER = os.path.join(APP_DIR, "images")
os.makedirs(IMAGE_FOLDER, exist_ok=True)

WINDOW_SIZE = (800, 800)
BG_COLOR = (249, 246, 238)
RADIUS = 400
MAX_IMG_SIZE = 128
MIN_SPEED = 80
MAX_SPEED = 160
FPS = 30
SCAN_INTERVAL = 1.0
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

# ---- Global paylaşılan dict (sadece referans olarak) ----
shared = {}

# ---- Pygame animasyon ----
def run_pygame(shared_dict):
    import pygame
    import io

    os.environ["SDL_VIDEODRIVER"] = "dummy"  # GUI'siz ortam için

    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("The tangible self video animation")
    clock = pygame.time.Clock()
    cx, cy = WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2

    def load_sprite(path: str):
        img = pygame.image.load(path).convert_alpha()
        w, h = img.get_size()
        scale = min(MAX_IMG_SIZE / max(w, h), 1.0)
        if scale < 1.0:
            img = pygame.transform.smoothscale(
                img, (round(w * scale), round(h * scale))
            )
        r_off = max(img.get_width(), img.get_height()) / 2
        eff_r = RADIUS - r_off
        dist = random.uniform(0, eff_r)
        angle = random.uniform(0, 2 * math.pi)
        x = cx + dist * math.cos(angle)
        y = cy + dist * math.sin(angle)
        speed = random.uniform(MIN_SPEED, MAX_SPEED)
        theta = random.uniform(0, 2 * math.pi)
        vx, vy = speed * math.cos(theta), speed * math.sin(theta)
        return {"img": img, "pos": [x, y], "vel": [vx, vy], "r_off": r_off}

    sprites: List[dict] = []
    loaded_files = set()

    def scan():
        for f in os.listdir(IMAGE_FOLDER):
            if f.lower().endswith(IMAGE_EXTS) and f not in loaded_files:
                try:
                    sprites.append(load_sprite(os.path.join(IMAGE_FOLDER, f)))
                    loaded_files.add(f)
                    print(f"➕  new image: {f}")
                except Exception as e:
                    print("load error:", e)

    scan()
    last_scan = time.time()
    running = True

    while running:
        dt = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        if time.time() - last_scan >= SCAN_INTERVAL:
            scan()
            last_scan = time.time()

        screen.fill(BG_COLOR)

        for sp in sprites:
            x, y = sp["pos"]
            vx, vy = sp["vel"]
            r_off = sp["r_off"]

            x += vx * dt
            y += vy * dt

            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            eff_r = RADIUS - r_off
            if dist > eff_r:
                nx, ny = dx / dist, dy / dist
                dot = vx * nx + vy * ny
                vx -= 2 * dot * nx
                vy -= 2 * dot * ny
                x = cx + nx * eff_r
                y = cy + ny * eff_r

            sp["pos"][0], sp["pos"][1] = x, y
            sp["vel"][0], sp["vel"][1] = vx, vy
            screen.blit(sp["img"], sp["img"].get_rect(center=(x, y)))
            # pygame.draw.circle(screen, (80, 80, 80), (cx, cy), RADIUS, 1)

        # Her frame'de JPEG olarak paylaş
        img_bytes = io.BytesIO()
        pygame.image.save(screen, img_bytes)
        img_bytes.seek(0)
        im = Image.open(img_bytes).convert("RGB")
        jpeg_bytes = io.BytesIO()
        im.save(jpeg_bytes, format="JPEG", quality=85)
        jpeg_bytes.seek(0)
        shared_dict['last_jpeg'] = jpeg_bytes.read()
        # print(f"Frame produced: {len(shared_dict['last_jpeg'])} bytes")
        pygame.display.flip()

    pygame.quit()

# ---- FastAPI uygulaması ----
app = FastAPI(title="The Tangible Self")

@app.on_event("startup")
def _start_pygame():
    manager = multiprocessing.Manager()
    shared_dict = manager.dict()
    pg_process = multiprocessing.Process(
        target=run_pygame, args=(shared_dict,), daemon=True
    )
    pg_process.start()
    shared["manager"] = manager
    shared["shared_dict"] = shared_dict
    shared["pg_process"] = pg_process
    print("🎮  Pygame process started")

@app.on_event("shutdown")
def _stop_pygame():
    pg_process = shared.get("pg_process")
    if pg_process and pg_process.is_alive():
        pg_process.terminate()
        pg_process.join()
        print("🛑  Pygame process terminated")

class ResponsePayload(BaseModel):
    responses: List[int]
    name: str

@app.post("/generate_noise")
def generate_noise(payload: ResponsePayload):
    if len(payload.responses) != 40 or not all(r in (0, 1) for r in payload.responses):
        raise HTTPException(status_code=400, detail="responses must be 40 elements of 0/1")

    # Dosya ismi: sadece harf/rakam/altçizgi
    import re
    def safe_filename(s):
        return re.sub(r'[^a-zA-Z0-9_-]', '_', s)[:40]
    base_name = safe_filename(payload.name)
    filename = f"circle_{base_name}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(IMAGE_FOLDER, filename)

    scale = sum(payload.responses) * 0.05

    try:
        save_circle_with_text_to_images(
            file_name=filename,
            text=payload.name,
            scale=scale
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "file": filename}


@app.get("/video_feed")
def video_feed():
    boundary = "frame"
    shared_dict = shared.get("shared_dict")
    def generate():
        while True:
            frame = shared_dict.get('last_jpeg', None)
            # print("Frame gönderiliyor", len(frame))
            # print(f"Frame produced: {len(shared_dict['last_jpeg'])} bytes")

            if frame:
                yield (
                    f"--{boundary}\r\n"
                    "Content-Type: image/jpeg\r\n\r\n"
                ).encode("utf-8") + frame + b"\r\n"
            time.sleep(1 / FPS)
    return StreamingResponse(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}"
    )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
