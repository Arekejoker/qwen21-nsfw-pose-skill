#!/usr/bin/env python3
"""Build side-by-side comparison sheets: author sample vs our phase5 reproduction."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).parent.parent
SAMPLES = BASE / "downloads/samples"
OUT = BASE / "outputs/phase5"

ROWS = [
    ("A1_shower_v13b", "taws_v13_shower_author.jpg", "A1 taws shower prompt · v1.3b@1.0 · 50s cfg2.5 er_sde/beta seed80964"),
    ("A2_massage_v13b", "taws_v13_massage_author.jpg", "A2 taws massage prompt · v1.3b@1.0 · 30s cfg2.5 er_sde/beta seed80964"),
    ("B1_selfie_seal", "thesealpacas_v2_selfie_author.jpg", "B1 thesealpacas selfie prompt · v2@0.8 · 50s cfg4 er_sde/beta"),
    ("C1_shower_no_lora", "taws_v13_shower_author.jpg", "C1 control: same shower prompt, NO LoRA"),
]

try:
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    FONT_S = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except OSError:
    FONT = ImageFont.load_default()
    FONT_S = ImageFont.load_default()


def load_fit(img_path: Path, max_w: int, max_h: int) -> Image.Image:
    im = Image.open(img_path).convert("RGB")
    im.thumbnail((max_w, max_h), Image.LANCZOS)
    return im


def main() -> None:
    cell_w, cell_h = 560, 780
    pad = 16
    header_h = 40
    rows = []
    for key, author_file, label in ROWS:
        author = SAMPLES / author_file
        ours = OUT / f"{key}.png"
        if not author.exists():
            print(f"skip {key}: missing author {author}")
            continue
        row = [load_fit(author, cell_w - 2 * pad, cell_h - 2 * pad - header_h)]
        if ours.exists() and ours.stat().st_size > 0:
            row.append(load_fit(ours, cell_w - 2 * pad, cell_h - 2 * pad - header_h))
        else:
            ph = Image.new("RGB", (cell_w - 2 * pad, cell_h - 2 * pad - header_h), (40, 40, 40))
            d = ImageDraw.Draw(ph)
            d.text((20, 20), "pending...", fill=(255, 255, 255), font=FONT_S)
            row.append(ph)
        rows.append((row, label))
    if not rows:
        print("no rows"); return
    n_rows = len(rows)
    W = 2 * cell_w + 3 * pad
    H = n_rows * (cell_h + 34) + 3 * pad
    sheet = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), "Left: author's sample (Civitai)   |   Right: our reproduction", fill=(255, 255, 255), font=FONT_S)
    y = 3 * pad + 34
    for row, label in rows:
        x = pad
        for im in row:
            sheet.paste(im, (x, y))
            d.rectangle([x, y, x + im.width - 1, y + im.height - 1], outline=(90, 90, 90), width=1)
            x += cell_w + pad
        d.text((pad, y + cell_h + 6), label, fill=(230, 230, 230), font=FONT_S)
        y += cell_h + 34
    sheet.save(OUT / "phase5_comparison.jpg", quality=88)
    print("saved", OUT / "phase5_comparison.jpg")


if __name__ == "__main__":
    main()
