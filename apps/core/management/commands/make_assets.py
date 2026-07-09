import base64
import io
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

NAVY = (10, 15, 30, 255)
AMBER = (255, 176, 31, 255)

PLANE_POINTS = [
    (2.01, 21.0),
    (23.0, 12.0),
    (2.01, 3.0),
    (2.0, 10.0),
    (17.0, 12.0),
    (2.0, 14.0),
]


def plane_polygon(size, inset=0.20):
    span = 1 - 2 * inset
    return [
        (round((inset + (x / 24) * span) * size), round((inset + (y / 24) * span) * size))
        for x, y in PLANE_POINTS
    ]


def build_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=NAVY)
    draw.polygon(plane_polygon(size), fill=AMBER)
    return img


class Command(BaseCommand):
    help = "Generate app icons for the kiosk PWA."

    def handle(self, *args, **options):
        icons_dir = Path(settings.BASE_DIR) / "static" / "img" / "icons"
        icons_dir.mkdir(parents=True, exist_ok=True)
        for size in (192, 512):
            build_icon(size).save(icons_dir / f"icon-{size}.png")
            self.stdout.write(f"icon written: {icons_dir / f'icon-{size}.png'}")
        self.stdout.write(self.style.SUCCESS("App icons ready."))
