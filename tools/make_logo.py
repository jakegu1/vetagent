"""A 400x400 icon for directory listings. Drawn, not downloaded, so it has no licence.

Cline's marketplace requires a 400x400 PNG. Several other directories take one too, and
a listing without an icon reads as abandoned next to ones that have it.

The shape is a shield with a check cut through it, in the landing page's own palette:
background #0B1110, accent #3FBFAA. Legible at 32px, which is the size it is actually
shown at in a marketplace list.
"""
import os

from PIL import Image, ImageDraw

BG = (11, 17, 16)
ACCENT = (63, 191, 170)
DIM = (27, 71, 64)
S = 400
SS = 4                                   # supersample, for clean edges without antialias


def shield(w, h, inset):
    """Points of a shield: flat shoulders, straight sides, a point at the bottom."""
    x0, x1 = inset, w - inset
    y0, y1 = inset, h - inset
    shoulder = y0 + (y1 - y0) * 0.62
    return [(x0, y0), (x1, y0), (x1, shoulder),
            ((x0 + x1) / 2.0, y1), (x0, shoulder)]


def main():
    size = S * SS
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)

    d.polygon(shield(size, size, 62 * SS), fill=DIM)
    d.polygon(shield(size, size, 62 * SS), outline=ACCENT, width=9 * SS)

    # NOT a checkmark. A checkmark reads as "approved", and the one thing this tool
    # is careful never to do is bless a token -- a critical check that could not run
    # comes back `unknown`, not "looks fine". Three bars in the verdict colours say
    # "this thing grades risk", which is what it does, and they stay legible at the
    # 32px a marketplace list actually renders.
    OK, WARN, CRIT = (79, 177, 131), (210, 160, 63), (224, 115, 106)
    bar_x0, bar_x1 = size * 0.335, size * 0.665
    for i, (colour, width_frac) in enumerate(
            ((OK, 1.00), (WARN, 0.74), (CRIT, 0.48))):
        y = size * (0.375 + i * 0.115)
        h = size * 0.052
        x1 = bar_x0 + (bar_x1 - bar_x0) * width_frac
        d.rounded_rectangle([bar_x0, y, x1, y + h], radius=h / 2.0, fill=colour)

    img = img.resize((S, S), Image.LANCZOS)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "assets", "logo-400.png")
    out = os.path.abspath(out)
    img.save(out, "PNG", optimize=True)
    print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))


if __name__ == "__main__":
    main()
