"""Tile images into a labelled contact sheet: python3 sheet.py out.jpg img1.png img2.png ... (label = file stem)."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

out, paths = sys.argv[1], sys.argv[2:]
cols, w, h = 5, 640, 360
sheet = Image.new("RGB", (cols * w, -(-len(paths) // cols) * (h + 24)), "#222")
draw = ImageDraw.Draw(sheet)
for i, p in enumerate(paths):
    x, y = (i % cols) * w, (i // cols) * (h + 24)
    sheet.paste(Image.open(p).convert("RGB").resize((w, h)), (x, y + 24))
    draw.text((x + 6, y + 6), Path(p).stem, fill="#fff")
sheet.save(out, quality=88)
