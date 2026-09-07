import base64
import io

import qrcode

QR_INK = "#0A0F1E"


def qr_data_uri(url, box_size=6, border=2):
    """Render ``url`` as a PNG data URI (same look as the printed QR markers)."""
    qr = qrcode.QRCode(border=border, box_size=box_size, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color=QR_INK, back_color="#FFFFFF").get_image()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
