"""Draws the TimeLog mark as PNG icons for the PWA manifest and the iOS home-screen icon (needs Pillow)."""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"


def draw(size: int, padding: float = 0.0) -> Image.Image:
    s = size * 4                                 # supersample for smooth edges
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # diagonal gradient background
    grad = Image.new("RGB", (s, s))
    px = grad.load()
    c1, c2 = (79, 70, 229), (124, 58, 237)
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * s)
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
    mask = Image.new("L", (s, s), 0)
    pad = int(s * padding)
    ImageDraw.Draw(mask).rounded_rectangle([pad, pad, s - pad - 1, s - pad - 1], radius=int((s - 2 * pad) * 0.24), fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    cx, cy, r = s / 2, s * 0.52, (s - 2 * pad) * 0.29
    w = int((s - 2 * pad) * 0.085)
    box = [cx - r, cy - r, cx + r, cy + r]
    d.ellipse(box, outline=(255, 255, 255, 56), width=w)
    d.arc(box, start=-90, end=-90 + 270, fill=(253, 186, 60, 255), width=w)
    hand = (255, 255, 255, 255)
    d.line([cx, cy, cx, cy - r * 0.53], fill=hand, width=int(w * 0.6))
    d.line([cx, cy, cx + r * 0.31, cy + r * 0.18], fill=hand, width=int(w * 0.6))
    d.ellipse([cx - w * 0.45, cy - w * 0.45, cx + w * 0.45, cy + w * 0.45], fill=hand)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(192).save(OUT / "icon-192.png")
    draw(512).save(OUT / "icon-512.png")
    draw(512, padding=0.1).save(OUT / "icon-maskable-512.png")
    draw(180).save(OUT / "apple-touch-icon.png")
    draw(64).save(OUT.parent / "favicon.png")
    print("icons written to", OUT)
