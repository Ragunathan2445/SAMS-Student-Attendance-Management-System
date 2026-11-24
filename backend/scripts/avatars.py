from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PALETTE = [
    ("#F3E6D8", "#8A5A35"), ("#EFE1D1", "#6B4226"), ("#F6EDE3", "#A06D43"), ("#EADBC8", "#5A3A25"),
    ("#F1E4D6", "#7A4E2D"), ("#E8D8C4", "#94633B"),
]
SKIN = ["#E8C3A0", "#D9A982", "#C68E66", "#B07850", "#E3B892", "#CF9C74"]


def _font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


SEED_PHOTO_DIR = Path(__file__).resolve().parents[1] / "seed_photos"


def place_photo(key: str, name: str, path: Path) -> bool:
    """Use backend/seed_photos/<key>.jpg|.jpeg|.png|.webp if present (e.g. student_6A01.jpg,
    teacher_T1001.png); otherwise draw a placeholder avatar. Returns True if a real photo was used."""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        src = SEED_PHOTO_DIR / f"{key}{ext}"
        if src.is_file():
            with Image.open(src) as img:
                img = img.convert("RGB")
                img.thumbnail((600, 600))
                path.parent.mkdir(parents=True, exist_ok=True)
                img.save(path, format="JPEG", quality=88)
            return True
    make_avatar(name, path)
    return False


def make_avatar(name: str, path: Path, size: int = 320) -> None:
    digest = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    bg, accent = PALETTE[digest % len(PALETTE)]
    skin = SKIN[(digest // 7) % len(SKIN)]
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    # shoulders / uniform
    d.ellipse([size * 0.12, size * 0.66, size * 0.88, size * 1.25], fill=accent)
    d.polygon([(size * 0.42, size * 0.68), (size * 0.5, size * 0.8), (size * 0.58, size * 0.68)], fill="#FFFFFF")
    # head and hair
    d.ellipse([size * 0.31, size * 0.2, size * 0.69, size * 0.62], fill=skin)
    d.chord([size * 0.29, size * 0.14, size * 0.71, size * 0.5], 180, 360, fill="#2E2018")
    # initials badge
    initials = "".join(p[0] for p in name.split()[:2]).upper()
    font = _font(int(size * 0.1))
    d.rounded_rectangle([size * 0.06, size * 0.06, size * 0.3, size * 0.2], radius=10, fill="#FFFFFF")
    tw = d.textlength(initials, font=font)
    d.text((size * 0.18 - tw / 2, size * 0.075), initials, fill=accent, font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=88)
