"""Genera iconos PNG para la PWA a partir del diseño SVG existente.

Uso:
    python scripts/generate_pwa_icons.py

Requiere Pillow (solo para generar los iconos, no en runtime de la app).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = Path(__file__).resolve().parent.parent / "src" / "web" / "static" / "icons"


def create_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg = (15, 23, 42)  # #0f172a
    accent = (56, 189, 248)  # #38bdf8
    detail = (51, 65, 85)  # #334155
    wheel = (226, 232, 240)  # #e2e8f0
    radius = size * 64 // 512

    # Fondo redondeado
    draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=bg)

    # Cuerpo del coche (parte inferior)
    body_top = size * 270 // 512
    body_height = size * 80 // 512
    body_left = size * 104 // 512
    body_right = size * 408 // 512
    draw.rounded_rectangle(
        [body_left, body_top, body_right, body_top + body_height],
        radius=size * 12 // 512,
        fill=detail,
    )

    # Cabina del coche
    cabin_top = size * 190 // 512
    cabin_height = size * 90 // 512
    cabin_left = size * 152 // 512
    cabin_right = size * 360 // 512
    draw.rounded_rectangle(
        [cabin_left, cabin_top, cabin_right, cabin_top + cabin_height],
        radius=size * 12 // 512,
        fill=accent,
    )

    # Ruedas
    wheel_r = size * 28 // 512
    wheel_y = body_top + body_height
    for cx in (size * 156 // 512, size * 356 // 512):
        draw.ellipse(
            [cx - wheel_r, wheel_y - wheel_r, cx + wheel_r, wheel_y + wheel_r],
            fill=wheel,
        )

    # Letra J
    font_size = size * 120 // 512
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    text = "J"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = size * 170 // 512 - text_h // 2
    draw.text((x, y), text, font=font, fill=(255, 255, 255))

    return img


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for name, size in [
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("apple-touch-icon.png", 180),
    ]:
        icon = create_icon(size)
        icon.save(ICONS_DIR / name)
        print(f"Generado {name} ({size}x{size})")


if __name__ == "__main__":
    main()
