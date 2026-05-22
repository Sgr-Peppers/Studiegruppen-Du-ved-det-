"""
VGG JSON → YOLO format konverter
---------------------------------
Konverterer Make Sense polygon-labels til YOLO bounding box .txt filer.
Søger automatisk i images/train/ og images/val/ efter billeder.
"""

import json
import os
from pathlib import Path

# ── Konfiguration ──────────────────────────────────────────────────────────────
JSON_FILE   = "labels_my-project-name_2026-05-22-01-19-14.json"
IMAGES_DIR = "C:/Users/surin/OneDrive/Skrivebord/yolo_training/dataset"
LABELS_DIR  = "labels"
CLASSES     = ["flame"]
# ──────────────────────────────────────────────────────────────────────────────

def get_image_size(image_path):
    from PIL import Image
    with Image.open(image_path) as img:
        return img.size  # (width, height)

def find_image(filename, images_dir):
    """Søger efter billedet i images/, images/train/ og images/val/"""
    search_dirs = [
        Path(images_dir),
        Path(images_dir) / "train",
        Path(images_dir) / "val",
    ]
    for d in search_dirs:
        p = d / filename
        if p.exists():
            return p
    return None

def polygon_to_bbox(xs, ys):
    return min(xs), min(ys), max(xs), max(ys)

def convert():
    os.makedirs(LABELS_DIR, exist_ok=True)

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    converted = 0
    skipped   = 0

    for filename, entry in data.items():
        regions = entry.get("regions", {})
        if not regions:
            print(f"  ⚠  Ingen regioner i {filename} — springer over")
            skipped += 1
            continue

        image_path = find_image(filename, IMAGES_DIR)
        if image_path is None:
            print(f"  ✗  Kunne ikke finde {filename} — springer over")
            skipped += 1
            continue

        img_w, img_h = get_image_size(image_path)

        lines = []
        for region in regions.values():
            shape = region["shape_attributes"]
            label = region["region_attributes"].get("label", "")

            if label not in CLASSES:
                print(f"  ⚠  Ukendt klasse '{label}' i {filename}")
                continue

            class_id = CLASSES.index(label)

            if shape["name"] == "polygon":
                xs = shape["all_points_x"]
                ys = shape["all_points_y"]
            elif shape["name"] == "rect":
                x, y, w, h = shape["x"], shape["y"], shape["width"], shape["height"]
                xs = [x, x + w]
                ys = [y, y + h]
            else:
                print(f"  ⚠  Ukendt shape '{shape['name']}' — springer over")
                continue

            x_min, y_min, x_max, y_max = polygon_to_bbox(xs, ys)

            cx = ((x_min + x_max) / 2) / img_w
            cy = ((y_min + y_max) / 2) / img_h
            bw = (x_max - x_min) / img_w
            bh = (y_max - y_min) / img_h

            cx = max(0.0, min(1.0, cx))
            cy = max(0.0, min(1.0, cy))
            bw = max(0.0, min(1.0, bw))
            bh = max(0.0, min(1.0, bh))

            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        if lines:
            stem = Path(filename).stem
            out_path = Path(LABELS_DIR) / f"{stem}.txt"
            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"  ✓  {filename} → {out_path.name}  ({len(lines)} label(s))")
            converted += 1
        else:
            skipped += 1

    print(f"\nFærdig! {converted} filer konverteret, {skipped} sprunget over.")
    print(f"Labels gemt i: {Path(LABELS_DIR).resolve()}")

if __name__ == "__main__":
    convert()
