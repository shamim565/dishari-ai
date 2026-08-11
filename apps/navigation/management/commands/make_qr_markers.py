import base64
import io
from pathlib import Path

import qrcode
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.navigation.models import Location


def build_qr(url):
    qr = qrcode.QRCode(border=2, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0A0F1E", back_color="#FFFFFF")
    return img.get_image()


def sheet_html(cards, base_url):
    tiles = []
    for loc in cards:
        tiles.append(
            f"""
    <div class="tile">
      <img src="data:image/png;base64,{loc['b64']}" alt="QR {loc['code']}">
      <p class="code">{loc['code']}</p>
      <p class="name">{loc['name_en']}</p>
      <p class="name bn">{loc['name_bn']}</p>
    </div>"""
        )
    return f"""<!doctype html>
<html lang="bn">
<head>
<meta charset="utf-8">
<title>Airport AI — QR Location Markers</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;600&family=Space+Grotesk:wght@400;600&display=swap" rel="stylesheet">
<style>
  body {{ margin: 0; font-family: "Space Grotesk", "Noto Sans Bengali", system-ui, sans-serif; background: #f8fafc; color: #0f172a; }}
  header {{ text-align: center; padding: 28px 20px 8px; }}
  header h1 {{ margin: 0 0 4px; font-size: 24px; }}
  header p {{ margin: 0; color: #64748b; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; padding: 20px 28px 36px; }}
  .tile {{ background: #fff; border: 1.5px dashed #94a3b8; border-radius: 16px; padding: 12px; text-align: center; break-inside: avoid; }}
  .tile img {{ width: 100%; max-width: 150px; image-rendering: pixelated; }}
  .code {{ margin: 6px 0 0; font-weight: 700; font-size: 15px; letter-spacing: .04em; }}
  .name {{ margin: 1px 0 0; font-size: 11px; color: #475569; }}
  .bn {{ font-family: "Noto Sans Bengali", sans-serif; }}
  @media print {{ body {{ background: #fff; }} .grid {{ padding: 10px; gap: 10px; }} }}
</style>
</head>
<body>
  <header>
    <h1>Scan for AI Navigation — ব্যানার / কলামে টাঙান</h1>
    <p>Each QR opens the Airport AI app and instantly sets the passenger's position · {base_url}/scan/&lt;code&gt;/</p>
  </header>
  <div class="grid">{''.join(tiles)}
  </div>
</body>
</html>
"""
