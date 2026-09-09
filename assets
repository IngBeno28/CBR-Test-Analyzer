"""
assets.py — brand assets for the CBR Test Analyzer's PDF report.

Houses the Automation_hub logo as an embedded base64 PNG (extracted from
the company's own report template) so the app has no dependency on an
external image file shipping alongside the code — report.py decodes it at
import time into an in-memory PNG that reportlab can place directly.

To swap in a different logo later: replace LOGO_PNG_BASE64 below with the
base64 of a new PNG (e.g. `base64.b64encode(open("logo.png","rb").read())`)
and nothing else needs to change — get_logo_bytes()/get_logo_image() stay
the same.
"""

import base64
import io

def get_logo_bytes() -> bytes:
    """Decode the embedded logo into raw PNG bytes."""
    return base64.b64decode(LOGO_PNG_BASE64)


def get_logo_image() -> io.BytesIO:
    """Decode the embedded logo into an in-memory file-like object, ready
    to hand to PIL.Image.open() or reportlab's Image() flowable."""
    return io.BytesIO(get_logo_bytes())
