"""
YOLO Label Editor - Fully Portable, No Hardcoded Paths
=======================================================
HOW IT FINDS YOUR DATASET (automatic, in this order):
  1. Reads saved path from ~/.yolo_editor_config.json  (remembered from last time)
  2. Looks for a dataset next to the script itself
  3. Shows a folder picker — you select the ROOT folder (e.g. the "golf" folder)
     and it auto-detects train/images, train/labels, valid/images, valid/labels

HOW IT FINDS YOUR CLASSES (automatic, in this order):
  1. Reads data.yaml from the root dataset folder
  2. Scans .txt label files and discovers class IDs
  3. Asks you to type class names manually

Works on ANY PC, ANY folder name, ANY number of classes.
No editing of the script is ever needed.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import cv2
import numpy as np
import os
import json
import shutil
import colorsys
from pathlib import Path
from PIL import Image, ImageTk

# Try importing yaml — ships with ultralytics but might be missing on some PCs
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("[Editor] pyyaml not installed — will discover classes from label files instead.")
    print("[Editor] To install: pip install pyyaml")


# ============================================================================
# CONFIG  (saved between sessions in your home folder as a small JSON file)
# ============================================================================

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".yolo_editor_config.json")

def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(data: dict):
    try:
        existing = load_config()
        existing.update(data)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        print(f"[Editor] Could not save config: {e}")


# ============================================================================
# DATASET STRUCTURE DETECTION
# ============================================================================

# All known YOLO folder layouts we try automatically
STRUCTURE_CANDIDATES = [
    # (train_images,     train_labels,     val_images,      val_labels)
    ("train/images",  "train/labels",  "valid/images",  "valid/labels"),
    ("train/images",  "train/labels",  "val/images",    "val/labels"),
    ("images/train",  "labels/train",  "images/val",    "labels/val"),
    ("images/train",  "labels/train",  "images/train",  "labels/train"),
    ("images",        "labels",        "images",        "labels"),
]

def detect_structure(root: str):
    """
    Given a root folder, find which YOLO layout is present.
    Also handles flat layouts (images/ + labels/ directly in root).
    Returns a paths dict or None.
    """
    root_path = Path(root)

    for img_tr, lbl_tr, img_val, lbl_val in STRUCTURE_CANDIDATES:
        p = {
            'img_train':   root_path / img_tr,
            'label_train': root_path / lbl_tr,
            'img_val':     root_path / img_val,
            'label_val':   root_path / lbl_val,
        }
        if p['img_train'].exists():
            for key in ('label_train', 'label_val'):
                p[key].mkdir(parents=True, exist_ok=True)
            result = {k: str(v) for k, v in p.items()}
            result['root'] = root
            print(f"[Editor] Structure matched ({img_tr}): {root}")
            return result

    # Fallback: user may have selected the images/ folder itself instead of root
    images = list(root_path.glob("*.jpg")) + list(root_path.glob("*.png")) + list(root_path.glob("*.jpeg"))
    if images:
        parent = root_path.parent
        sibling_labels = parent / "labels"
        sibling_labels.mkdir(parents=True, exist_ok=True)
        result = {
            'img_train':   str(root_path),
            'label_train': str(sibling_labels),
            'img_val':     str(root_path),
            'label_val':   str(sibling_labels),
            'root':        str(parent),
        }
        print(f"[Editor] Treating selected folder as images folder, root={parent}")
        return result

    return None

def pick_dataset_root():
    """Show a GUI folder picker. Returns path string or None."""
    tmp = tk.Tk()
    tmp.withdraw()
    folder = filedialog.askdirectory(
        title="Select your DATASET ROOT folder  (e.g. the 'golf' folder containing 'train' inside)"
    )
    tmp.destroy()
    return folder if folder else None

def resolve_dataset(config: dict):
    """
    Full pipeline:
      1. Try remembered path from last session
      2. Try folder next to the script
      3. Ask the user to pick a folder
    """
    # Step 1: remembered
    last_root = config.get('last_root')
    if last_root and os.path.isdir(last_root):
        paths = detect_structure(last_root)
        if paths:
            print(f"[Editor] Using remembered dataset: {last_root}")
            return paths

    # Step 2: next to script — also try the script's own folder as the root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths = detect_structure(script_dir)
    if paths:
        save_config({'last_root': paths['root']})
        return paths

    # Step 3: ask user
    print("[Editor] No dataset found automatically — opening folder picker")
    while True:
        root = pick_dataset_root()
        if not root:
            return None  # User cancelled

        paths = detect_structure(root)
        if paths:
            save_config({'last_root': root})
            return paths

        messagebox.showerror(
            "Dataset Not Found",
            f"Could not find a YOLO dataset structure in:\n{root}\n\n"
            "Expected one of these layouts inside that folder:\n"
            "  • train/images/  +  train/labels/\n"
            "  • images/train/  +  labels/train/\n\n"
            "Please select the ROOT folder that contains a 'train' subfolder inside it."
        )


# ============================================================================
# CLASS DETECTION
# ============================================================================

def _parse_yaml_names_manually(yaml_path: str):
    """
    Fallback YAML parser that requires NO third-party libraries.

    YOLO data.yaml always has a 'names:' line in one of two formats:
      Format A (list):   names: ['cat', 'dog', 'bird']
      Format B (block):  names:
                           - cat
                           - dog

    We handle both without needing pyyaml installed.
    Returns a list of name strings, or None if parsing fails.
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        names = []

        # ── Format A: names: ['cat', 'dog']  or  names: [cat, dog] ──────────
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('names:') and '[' in stripped:
                # Extract everything between [ and ]
                inside = stripped[stripped.index('[') + 1 : stripped.rindex(']')]
                # Split on commas, strip quotes and whitespace
                parts = [p.strip().strip("'\"") for p in inside.split(',')]
                names = [p for p in parts if p]
                if names:
                    print(f"[Editor] Parsed names (Format A) from: {yaml_path}")
                    return names

        # ── Format B: names:\n  - cat\n  - dog   (list block) ─────────────────
        # ── Format C: names:\n  0: cat\n  1: dog  (dict block) ────────────────
        in_names_block = False
        list_entries = []
        dict_entries = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('names:'):
                in_names_block = True
                continue
            if in_names_block:
                if stripped.startswith('-'):
                    name = stripped[1:].strip().strip("'\"")
                    if name:
                        list_entries.append(name)
                elif ':' in stripped and not stripped.startswith('#'):
                    key_part, _, val_part = stripped.partition(':')
                    key_s = key_part.strip()
                    val_s = val_part.strip().strip("'\"")
                    if key_s.isdigit() and val_s:
                        dict_entries[int(key_s)] = val_s
                    elif line and not line[0].isspace():
                        break
                elif stripped and not stripped.startswith('#'):
                    if line and not line[0].isspace():
                        break

        if dict_entries:
            names = [dict_entries[k] for k in sorted(dict_entries.keys())]
            print(f"[Editor] Parsed names (dict block) from: {yaml_path}")
            return names
        if list_entries:
            names = list_entries
            print(f"[Editor] Parsed names (list block) from: {yaml_path}")
            return names
            return names

    except Exception as e:
        print(f"[Editor] Manual YAML parse error for {yaml_path}: {e}")

    return None


def _find_all_yaml_files(root: str):
    """
    Walk from root upward AND also check inside the root folder itself.
    Returns a list of existing data.yaml paths to try, in priority order.
    """
    candidates = []
    p = Path(root)

    # Walk upward 6 levels
    current = p
    for _ in range(7):
        candidate = current / "data.yaml"
        if candidate.exists():
            candidates.append(candidate)
        current = current.parent

    return candidates


def load_classes_from_yaml(root: str):
    """
    Find and parse data.yaml — works with OR without pyyaml installed.

    Priority:
      1. Use pyyaml if available (most reliable)
      2. Fall back to our manual parser (no dependencies needed)

    Searches the root folder and up to 6 parent levels.
    Prints exactly what it finds and why it fails so debugging is easy.
    """
    yaml_files = _find_all_yaml_files(root)

    if not yaml_files:
        print(f"[Editor] No data.yaml found in {root} or any parent folders")
        return None

    for yaml_path in yaml_files:
        print(f"[Editor] Found data.yaml at: {yaml_path}")

        names = None

        # ── Try pyyaml first ─────────────────────────────────────────────────
        if HAS_YAML:
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict):
                    print(f"[Editor]   pyyaml returned {type(data).__name__} (not a dict) — trying manual parser")
                else:
                    raw_names = data.get('names', [])
                    if raw_names:
                        names = [str(n) for n in raw_names]
                        print(f"[Editor]   pyyaml parsed {len(names)} classes: {names}")
                    else:
                        print(f"[Editor]   pyyaml found no 'names' key — trying manual parser")

            except Exception as e:
                print(f"[Editor]   pyyaml error: {e} — trying manual parser")

        # ── Fall back to manual parser if needed ─────────────────────────────
        if not names:
            names = _parse_yaml_names_manually(str(yaml_path))
            if names:
                print(f"[Editor]   Manual parser found {len(names)} classes: {names}")
            else:
                print(f"[Editor]   Manual parser also failed — skipping this file")
                continue

        # ── Success ───────────────────────────────────────────────────────────
        return {i: str(name) for i, name in enumerate(names)}

    return None


def load_classes_from_labels(label_folder: str):
    """Scan .txt files and collect all class IDs that appear in them."""
    class_ids = set()
    if not os.path.isdir(label_folder):
        print(f"[Editor] Label folder not found: {label_folder}")
        return None

    txt_files = [f for f in os.listdir(label_folder) if f.endswith('.txt')]
    print(f"[Editor] Scanning {len(txt_files)} label files in: {label_folder}")

    for fname in txt_files:
        try:
            with open(os.path.join(label_folder, fname), 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        class_ids.add(int(parts[0]))
        except Exception:
            pass

    if not class_ids:
        print(f"[Editor] No class IDs found in label files")
        return None

    print(f"[Editor] Discovered class IDs from labels: {sorted(class_ids)}")
    return {cid: f"class_{cid}" for cid in sorted(class_ids)}


def ask_user_for_classes(root_hint: str = ""):
    """
    Show a dialog for the user to type class names manually.
    After the user confirms, the classes are saved into data.yaml automatically
    so next launch loads them without asking again.
    """
    tmp = tk.Tk()
    tmp.withdraw()

    # Check if data.yaml exists but is empty — give a clearer message
    yaml_path = os.path.join(root_hint, "data.yaml")
    if os.path.exists(yaml_path):
        size = os.path.getsize(yaml_path)
        extra = f"data.yaml found but is EMPTY ({size} bytes).\nIt will be filled in automatically.\n\n"
    else:
        extra = "No data.yaml found yet — one will be created automatically.\n\n"

    answer = simpledialog.askstring(
        "Enter Class Names",
        f"Dataset:  {root_hint}\n\n"
        + extra +
        "Type your class names separated by commas:\n"
        "Example:  cat, dog, bird\n\n"
        "Class 0 = first name,  Class 1 = second, etc.",
        parent=tmp
    )
    tmp.destroy()

    if not answer:
        return {0: 'object'}
    names = [n.strip() for n in answer.split(',') if n.strip()]
    if not names:
        return {0: 'object'}

    class_map = {i: name for i, name in enumerate(names)}

    # Write classes into data.yaml so next launch finds them automatically
    _write_data_yaml(root_hint, names)

    return class_map


def _write_data_yaml(root: str, names: list):
    """Write a minimal data.yaml with the class names into the dataset root."""
    yaml_path = os.path.join(root, "data.yaml")
    try:
        lines = [
            f"nc: {len(names)}",
            "names: [" + ", ".join(f"'{n}'" for n in names) + "]",
            "",
            "# Paths (adjust if needed)",
            "train: images",
            "val: images",
        ]
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"[Editor] Wrote data.yaml: {yaml_path}")
    except Exception as e:
        print(f"[Editor] Could not write data.yaml: {e}")

def resolve_classes(paths: dict):
    """Try all three class-detection methods and return class_names + class_colors."""
    root = paths['root']

    class_names = (
        load_classes_from_yaml(root)
        or load_classes_from_labels(paths['label_train'])
        or ask_user_for_classes(root)
    )

    max_id  = max(class_names.keys()) + 1
    palette = _generate_colors(max_id)
    class_colors = {cid: palette[cid] for cid in class_names}

    print(f"[Editor] Final class map: {class_names}")
    return class_names, class_colors

def _generate_colors(n: int):
    """Return n visually distinct hex colors spread evenly around the HSV wheel."""
    colors = []
    for i in range(max(n, 1)):
        h = i / max(n, 1)
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.95)
        colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return colors


# ============================================================================
# MAIN EDITOR CLASS
# ============================================================================

class YOLOLabelEditor:

    def __init__(self, root_window):
        self.root   = root_window
        self.config = load_config()

        # ── 1. Find dataset ───────────────────────────────────────────────────
        self.paths = resolve_dataset(self.config)
        if not self.paths:
            messagebox.showerror("Cancelled", "No dataset selected. Closing.")
            self.root.destroy()
            return

        self.IMAGE_FOLDER = self.paths['img_train']
        self.LABEL_FOLDER = self.paths['label_train']

        # ── 2. Find classes ───────────────────────────────────────────────────
        self.CLASS_NAMES, self.CLASS_COLORS = resolve_classes(self.paths)

        # ── 3. State ──────────────────────────────────────────────────────────
        self.image_x     = 0
        self.image_y     = 0
        self.zoom_scale  = 1.0
        self.pan_start_x = None
        self.pan_start_y = None

        self.hovered_box        = None
        self.current_image      = None
        self.current_image_path = None
        self.current_label_path = None
        self.boxes       = []
        self.drawing     = False
        self.dragging    = False
        self.resizing    = False
        self.selected_box   = None
        self.drag_start_x   = None
        self.drag_start_y   = None
        self.resize_corner  = None
        self.box_drag_start = None

        self.image_folder        = None
        self.image_files         = []
        self.current_image_index = -1

        self.selected_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "selected_images"
        )
        self.selected_class = min(self.CLASS_NAMES.keys())
        self.class_var = tk.IntVar(value=self.selected_class)

        # ── 4. Build UI ───────────────────────────────────────────────────────
        self._update_title()
        self.create_gui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Prior>", self.move_current_image)   # Page Up

        self.load_folder()

    # =========================================================================
    # TITLE BAR
    # =========================================================================

    def _update_title(self, image_name=""):
        dataset_name  = os.path.basename(self.paths['root'])
        classes_str   = "  |  ".join(
            f"{cid}:{name}" for cid, name in sorted(self.CLASS_NAMES.items())
        )
        suffix = f"  —  {image_name}" if image_name else ""
        self.root.title(f"YOLO Editor  [{dataset_name}]  |  {classes_str}{suffix}")

    # =========================================================================
    # GUI
    # =========================================================================

    def create_gui(self):
        btn = {'width': 8, 'height': 1, 'font': ('Arial', 8)}

        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(main, bg='#2b2b2b')
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        row1 = tk.Frame(toolbar, bg='#2b2b2b')
        row1.pack(side=tk.TOP, fill=tk.X)

        row2 = tk.Frame(toolbar, bg='#2b2b2b')
        row2.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))

        # ── Row 1: navigation ─────────────────────────────────────────────────
        nav = tk.Frame(row1, bg='#2b2b2b')
        nav.pack(side=tk.LEFT, padx=2)

        # Dataset switcher button
        tk.Button(nav, text="📁 Dataset",
                  command=self.switch_dataset,
                  width=9, height=1, font=('Arial', 8),
                  bg='#555', fg='white').pack(side=tk.LEFT, padx=1)

        for text, cmd in [
            ("Move(PgUp)", lambda: self.move_current_image(None)),
            ("⏮ First",   self.goto_first_image),
            ("◀◀ -100",   lambda: self.jump_images(-100)),
            ("← Prev",    self.prev_image),
            ("Next →",    self.next_image),
            ("+100 ▶▶",   lambda: self.jump_images(100)),
            ("Last ⏭",    self.goto_last_image),
        ]:
            tk.Button(nav, text=text, command=cmd, **btn).pack(side=tk.LEFT, padx=1)

        self.image_info = tk.StringVar(value="No images loaded")
        tk.Label(nav, textvariable=self.image_info,
                 font=('Arial', 8), bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=8)

        tk.Button(nav, text="Reset Zoom", command=self.reset_zoom, **btn).pack(side=tk.LEFT, padx=1)

        # Current dataset path shown in grey
        self.dataset_label_var = tk.StringVar(value=f"📂 {self.paths['root']}")
        tk.Label(nav, textvariable=self.dataset_label_var,
                 font=('Arial', 7), bg='#2b2b2b', fg='#aaaaaa').pack(side=tk.LEFT, padx=8)

        help_btn = tk.Button(nav, text="?", width=2, height=1, font=('Arial', 8, 'bold'))
        help_btn.pack(side=tk.LEFT, padx=5)
        self._bind_help_tooltip(help_btn)

        # ── Row 2: class selector (rebuilt dynamically) ───────────────────────
        self.class_row = row2
        self._build_class_selector()

        # ── Canvas area ───────────────────────────────────────────────────────
        canvas_frame = tk.Frame(main)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.v_scrollbar = tk.Scrollbar(canvas_frame)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(canvas_frame, cursor="cross",
                                xscrollcommand=self.h_scrollbar.set,
                                yscrollcommand=self.v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.h_scrollbar.config(command=self.canvas.xview)
        self.v_scrollbar.config(command=self.canvas.yview)

        self.bind_events()

    def _build_class_selector(self):
        """Destroy old class buttons and build fresh ones from CLASS_NAMES."""
        for w in self.class_row.winfo_children():
            w.destroy()

        tk.Label(self.class_row, text="  Draw class:",
                 font=('Arial', 8, 'bold'),
                 bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=(4, 2))

        # Scrollable container — handles 50+ classes without overflow
        sc  = tk.Frame(self.class_row, bg='#2b2b2b')
        sc.pack(side=tk.LEFT, fill=tk.X, expand=True)

        cvs = tk.Canvas(sc, height=28, highlightthickness=0, bg='#2b2b2b')
        hsb = tk.Scrollbar(sc, orient=tk.HORIZONTAL, command=cvs.xview)
        cvs.configure(xscrollcommand=hsb.set)

        if len(self.CLASS_NAMES) > 8:
            hsb.pack(side=tk.BOTTOM, fill=tk.X)
        cvs.pack(side=tk.TOP, fill=tk.X, expand=True)

        inner  = tk.Frame(cvs, bg='#2b2b2b')
        win_id = cvs.create_window((0, 0), window=inner, anchor='nw')
        inner.bind("<Configure>", lambda e: cvs.configure(scrollregion=cvs.bbox("all")))
        cvs.bind("<Configure>",   lambda e: cvs.itemconfig(win_id, width=e.width))

        for cid in sorted(self.CLASS_NAMES.keys()):
            name  = self.CLASS_NAMES[cid]
            color = self.CLASS_COLORS.get(cid, '#ffffff')
            tk.Radiobutton(
                inner,
                text=f"{name}  ({cid})",
                variable=self.class_var,
                value=cid,
                fg=color,
                bg='#2b2b2b',
                selectcolor='#444',
                activebackground='#2b2b2b',
                font=('Arial', 8, 'bold'),
                command=lambda c=cid: self._select_class(c)
            ).pack(side=tk.LEFT, padx=4)

        # Number key shortcuts 0-9 → instant class switch
        for digit in range(10):
            self.root.bind(str(digit), lambda e, d=digit: self._select_class_by_key(d))

    def _bind_help_tooltip(self, btn):
        text = (
            "Controls:\n"
            "• Left drag (empty area): Draw new box\n"
            "• Left drag (on box):     Move box\n"
            "• Left drag (corner):     Resize box\n"
            "• Q:                      Delete hovered box\n"
            "• Scroll wheel:           Zoom in/out\n"
            "• Right drag:             Pan view\n"
            "• ← →  or  Space:        Navigate images\n"
            "• Page Up:                Move image to selected_images/\n"
            "• Keys 0-9:               Quick-select class by number\n"
            "• 📁 Dataset button:      Switch to a different dataset folder"
        )
        def show(event):
            tip = tk.Toplevel()
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root+12}+{event.y_root+12}")
            tip.configure(bg='lightyellow')
            tk.Label(tip, text=text, justify=tk.LEFT,
                     font=('Arial', 8), bg='lightyellow', padx=6, pady=6).pack()
            def hide(e=None): tip.destroy()
            tip.bind('<Leave>', hide)
            btn.bind('<Leave>', hide)
        btn.bind('<Enter>', show)

    def _select_class(self, cid):
        if cid in self.CLASS_NAMES:
            self.selected_class = cid
            self.class_var.set(cid)

    def _select_class_by_key(self, digit):
        if digit in self.CLASS_NAMES:
            self._select_class(digit)

    # =========================================================================
    # DATASET SWITCHING (📁 button at runtime)
    # =========================================================================

    def switch_dataset(self):
        """Pick a new root folder and reload everything without restarting."""
        self.save_labels(force_save=True)

        folder = pick_dataset_root()
        if not folder:
            return

        paths = detect_structure(folder)
        if not paths:
            messagebox.showerror(
                "Not Found",
                f"No YOLO structure found in:\n{folder}\n\n"
                "Expected 'train/images' inside it."
            )
            return

        save_config({'last_root': folder})
        self.paths        = paths
        self.IMAGE_FOLDER = paths['img_train']
        self.LABEL_FOLDER = paths['label_train']

        self.CLASS_NAMES, self.CLASS_COLORS = resolve_classes(paths)
        self.selected_class = min(self.CLASS_NAMES.keys())
        self.class_var.set(self.selected_class)

        self.dataset_label_var.set(f"📂 {folder}")
        self._build_class_selector()
        self._update_title()

        self.image_files         = []
        self.current_image_index = -1
        self.boxes               = []
        self.canvas.delete("all")
        self.image_info.set("Loading...")
        self.load_folder()

    # =========================================================================
    # IMAGE LOADING
    # =========================================================================

    def load_folder(self):
        folder = self.IMAGE_FOLDER
        if not os.path.isdir(folder):
            messagebox.showerror("Folder Not Found",
                                 f"Image folder not found:\n{folder}")
            return

        self.image_folder = folder
        self.image_files  = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.jpegfile'))
        ])

        if not self.image_files:
            messagebox.showwarning("No Images", f"No images found in:\n{folder}")
            return

        last_idx = self.config.get('last_index', 0)
        self.current_image_index = min(last_idx, len(self.image_files) - 1)
        self.load_image(self.current_image_index)

    def load_image(self, index):
        if not self.image_files or index < 0 or index >= len(self.image_files):
            return

        self.current_image_path = self.image_files[index]
        image_name = os.path.basename(self.current_image_path)
        label_name = os.path.splitext(image_name)[0] + '.txt'
        self.current_label_path = os.path.join(self.LABEL_FOLDER, label_name)

        self.current_image = self._safe_read_image(self.current_image_path)
        if self.current_image is None:
            print(f"[Editor] Could not read: {self.current_image_path}")
            return

        self.boxes = []
        if os.path.exists(self.current_label_path):
            self.load_labels()

        self.image_info.set(f"Image {index + 1}/{len(self.image_files)}: {image_name}")
        self._update_title(image_name)
        self.display_image()

    def _safe_read_image(self, path):
        try:
            img = cv2.imread(str(path))
            if img is not None:
                return img
            with open(path, 'rb') as f:
                arr = np.asarray(bytearray(f.read()), dtype=np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"[Editor] Read error {path}: {e}")
            return None

    # =========================================================================
    # LABEL I/O
    # =========================================================================

    def load_labels(self):
        """
        YOLO format: class_id  cx  cy  w  h  (normalized 0-1)
        Converts to pixel top-left + width/height.
        """
        if self.current_image is None:
            return
        ih, iw = self.current_image.shape[:2]
        self.boxes = []
        with open(self.current_label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    cid = int(parts[0])
                    cx, cy, bw, bh = map(float, parts[1:])
                    x = (cx - bw / 2) * iw
                    y = (cy - bh / 2) * ih
                    w = bw * iw
                    h = bh * ih
                    self.boxes.append((cid, x, y, w, h))

    def save_labels(self, force_save=False):
        """Converts pixel coords back to normalized YOLO format and writes file."""
        if not self.current_label_path or self.current_image is None:
            return
        if not force_save and not self.boxes:
            return
        ih, iw = self.current_image.shape[:2]
        os.makedirs(os.path.dirname(self.current_label_path), exist_ok=True)
        with open(self.current_label_path, 'w') as f:
            for cid, x, y, w, h in self.boxes:
                cx = (x + w / 2) / iw
                cy = (y + h / 2) / ih
                nw = w / iw
                nh = h / ih
                f.write(f"{cid} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")

    # =========================================================================
    # RENDERING
    # =========================================================================

    def display_image(self):
        self.canvas.delete("all")
        self.reset_zoom()

    def reset_zoom(self):
        self.zoom_scale = 1.0
        self.image_x    = 0
        self.image_y    = 0
        self.render_image()

    def render_image(self):
        if self.current_image is None:
            return
        ih, iw = self.current_image.shape[:2]
        nw = int(iw * self.zoom_scale)
        nh = int(ih * self.zoom_scale)
        resized = cv2.resize(self.current_image, (nw, nh))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self.tk_image = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.canvas.delete("all")
        self.canvas.create_image(self.image_x, self.image_y,
                                 anchor=tk.NW, image=self.tk_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.draw_boxes()

    def draw_boxes(self):
        self.canvas.delete("box")
        self.canvas.delete("label")
        for cid, x, y, w, h in self.boxes:
            color = self.CLASS_COLORS.get(cid, '#ffffff')
            name  = self.CLASS_NAMES.get(cid, f"class_{cid}")
            cx = x * self.zoom_scale + self.image_x
            cy = y * self.zoom_scale + self.image_y
            cw = w * self.zoom_scale
            ch = h * self.zoom_scale
            self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch,
                                         outline=color, width=2, tags="box")
            self.canvas.create_text(cx+2, cy+2, anchor=tk.NW,
                                    text=f"{name} ({cid})",
                                    fill=color, font=('Arial', 8, 'bold'), tags="label")
            self._draw_handles(cx, cy, cw, ch, color)

    def _draw_handles(self, x, y, w, h, color):
        s = 5
        for px, py in [
            (x,     y),     (x+w/2, y),     (x+w, y),
            (x,     y+h/2),                  (x+w, y+h/2),
            (x,     y+h),   (x+w/2, y+h),  (x+w, y+h),
        ]:
            self.canvas.create_rectangle(px-s, py-s, px+s, py+s,
                                         fill=color, outline=color, tags="box")

    # =========================================================================
    # NAVIGATION
    # =========================================================================

    def goto_first_image(self):
        self.current_image_index = 0
        self.load_image(self.current_image_index)

    def goto_last_image(self):
        self.current_image_index = len(self.image_files) - 1
        self.load_image(self.current_image_index)

    def prev_image(self):
        if self.current_image_index > 0:
            self.save_labels(force_save=True)
            self.current_image_index -= 1
            self.load_image(self.current_image_index)

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.save_labels(force_save=True)
            self.current_image_index += 1
            self.load_image(self.current_image_index)

    def jump_images(self, amount):
        new = max(0, min(len(self.image_files) - 1, self.current_image_index + amount))
        if new != self.current_image_index:
            self.save_labels(force_save=True)
            self.current_image_index = new
            self.load_image(self.current_image_index)

    def move_current_image(self, event):
        """Page Up — move current image + label to selected_images/ folder."""
        if not self.current_image_path or not self.image_files:
            return
        os.makedirs(self.selected_folder, exist_ok=True)
        try:
            img_name = os.path.basename(self.current_image_path)
            lbl_name = os.path.splitext(img_name)[0] + '.txt'
            lbl_path = os.path.join(self.LABEL_FOLDER, lbl_name)
            shutil.move(self.current_image_path,
                        os.path.join(self.selected_folder, img_name))
            if os.path.exists(lbl_path):
                shutil.move(lbl_path, os.path.join(self.selected_folder, lbl_name))
            self.image_files.pop(self.current_image_index)
            if self.current_image_index >= len(self.image_files):
                self.current_image_index = len(self.image_files) - 1
            if self.image_files:
                self.load_image(self.current_image_index)
            else:
                self.canvas.delete("all")
                self.image_info.set("No images remaining")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to move image:\n{e}")

    # =========================================================================
    # EVENT BINDING
    # =========================================================================

    def bind_events(self):
        self.canvas.bind("<ButtonPress-1>",   self.start_operation)
        self.canvas.bind("<B1-Motion>",       self.during_operation)
        self.canvas.bind("<ButtonRelease-1>", self.end_operation)
        self.canvas.bind("<ButtonPress-3>",   self.start_pan)
        self.canvas.bind("<B3-Motion>",       self.do_pan)
        self.canvas.bind("<ButtonRelease-3>", self.end_pan)
        self.canvas.bind("<MouseWheel>",      self.zoom)
        self.canvas.bind("<Motion>",          self.on_mouse_move)
        self.root.bind("<Left>",  lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        self.root.bind("<space>", lambda e: self.next_image())
        self.root.bind("q",       self.delete_hovered_box)
        self.root.bind("Q",       self.delete_hovered_box)

    def start_pan(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def do_pan(self, event):
        if self.pan_start_x is not None:
            self.image_x += event.x - self.pan_start_x
            self.image_y += event.y - self.pan_start_y
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.render_image()

    def end_pan(self, event):
        self.pan_start_x = None
        self.pan_start_y = None

    def zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_scale = max(0.1, min(self.zoom_scale * factor, 10.0))
        self.render_image()

    def on_mouse_move(self, event):
        self.hovered_box = self.get_box_at_position(
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y)
        )

    def delete_hovered_box(self, event):
        if self.hovered_box is not None and self.hovered_box < len(self.boxes):
            self.boxes.pop(self.hovered_box)
            self.hovered_box = None
            self.draw_boxes()
            self.save_labels(force_save=True)

    def get_box_at_position(self, cx, cy):
        for i, (_, x, y, w, h) in enumerate(self.boxes):
            bx = x * self.zoom_scale + self.image_x
            by = y * self.zoom_scale + self.image_y
            bw = w * self.zoom_scale
            bh = h * self.zoom_scale
            if bx <= cx <= bx+bw and by <= cy <= by+bh:
                return i
        return None

    def get_resize_corner(self, cx, cy):
        threshold = 8
        for i, (_, x, y, w, h) in enumerate(self.boxes):
            bx = x * self.zoom_scale + self.image_x
            by = y * self.zoom_scale + self.image_y
            bw = w * self.zoom_scale
            bh = h * self.zoom_scale
            handles = {
                'tl': (bx,      by),      'tm': (bx+bw/2, by),      'tr': (bx+bw, by),
                'ml': (bx,      by+bh/2),                            'mr': (bx+bw, by+bh/2),
                'bl': (bx,      by+bh),   'bm': (bx+bw/2, by+bh),  'br': (bx+bw, by+bh),
            }
            for corner, (hx, hy) in handles.items():
                if abs(cx-hx) <= threshold and abs(cy-hy) <= threshold:
                    return i, corner
        return None, None

    def start_operation(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        box_idx, corner = self.get_resize_corner(cx, cy)
        if box_idx is not None:
            self.resizing = True
            self.selected_box  = box_idx
            self.resize_corner = corner
            self.drag_start_x  = cx
            self.drag_start_y  = cy
            self.canvas.config(cursor="sizing")
            return
        box_idx = self.get_box_at_position(cx, cy)
        if box_idx is not None:
            self.dragging     = True
            self.selected_box = box_idx
            self.drag_start_x = cx
            self.drag_start_y = cy
            self.box_drag_start = self.boxes[box_idx][1:]
            self.canvas.config(cursor="fleur")
            return
        self.drawing = True
        self.start_x = (cx - self.image_x) / self.zoom_scale
        self.start_y = (cy - self.image_y) / self.zoom_scale
        self.temp_box = None
        self.canvas.config(cursor="cross")

    def during_operation(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if self.resizing and self.selected_box is not None:
            self.resize_box(cx, cy)
        elif self.dragging and self.selected_box is not None:
            self.drag_box(cx, cy)
        elif self.drawing:
            self.draw_new_box(cx, cy)

    def end_operation(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if self.resizing:
            self.resizing = False
            self.selected_box  = None
            self.resize_corner = None
            self.canvas.config(cursor="cross")
            self.save_labels(force_save=True)
        elif self.dragging:
            self.dragging     = False
            self.selected_box = None
            self.box_drag_start = None
            self.canvas.config(cursor="cross")
            self.save_labels(force_save=True)
        elif self.drawing:
            self.drawing = False
            if self.temp_box:
                self.canvas.delete(self.temp_box)
                cur_x = (cx - self.image_x) / self.zoom_scale
                cur_y = (cy - self.image_y) / self.zoom_scale
                x = min(self.start_x, cur_x)
                y = min(self.start_y, cur_y)
                w = abs(cur_x - self.start_x)
                h = abs(cur_y - self.start_y)
                if self.current_image is not None:
                    ih, iw = self.current_image.shape[:2]
                    x = max(0, min(x, iw))
                    y = max(0, min(y, ih))
                    w = min(w, iw - x)
                    h = min(h, ih - y)
                if w >= 2 and h >= 2:
                    self.boxes.append((self.selected_class, x, y, w, h))
                    self.draw_boxes()
                    self.save_labels(force_save=True)
            self.canvas.config(cursor="cross")

    def resize_box(self, cx, cy):
        if self.selected_box is None or self.resize_corner is None:
            return
        cid, x, y, w, h = self.boxes[self.selected_box]
        dx = (cx - self.drag_start_x) / self.zoom_scale
        dy = (cy - self.drag_start_y) / self.zoom_scale
        ih, iw = self.current_image.shape[:2]
        nx, ny, nw, nh = x, y, w, h
        if self.resize_corner in ('tl', 'ml', 'bl'):
            nx = min(max(0, x+dx), x+w-2);  nw = w - (nx - x)
        if self.resize_corner in ('tr', 'mr', 'br'):
            nw = min(max(2, w+dx), iw-x)
        if self.resize_corner in ('tl', 'tm', 'tr'):
            ny = min(max(0, y+dy), y+h-2);  nh = h - (ny - y)
        if self.resize_corner in ('bl', 'bm', 'br'):
            nh = min(max(2, h+dy), ih-y)
        if nw >= 2 and nh >= 2:
            self.boxes[self.selected_box] = (cid, nx, ny, nw, nh)
            self.draw_boxes()
            self.drag_start_x = cx
            self.drag_start_y = cy

    def drag_box(self, cx, cy):
        dx = (cx - self.drag_start_x) / self.zoom_scale
        dy = (cy - self.drag_start_y) / self.zoom_scale
        ox, oy, w, h = self.box_drag_start
        nx, ny = ox+dx, oy+dy
        if self.current_image is not None:
            ih, iw = self.current_image.shape[:2]
            nx = max(0, min(nx, iw-w))
            ny = max(0, min(ny, ih-h))
        self.boxes[self.selected_box] = (self.boxes[self.selected_box][0], nx, ny, w, h)
        self.draw_boxes()

    def draw_new_box(self, cx, cy):
        """Live preview of the box being drawn, colored by the active class."""
        if self.temp_box:
            self.canvas.delete(self.temp_box)
        ex = (cx - self.image_x) / self.zoom_scale
        ey = (cy - self.image_y) / self.zoom_scale
        if self.current_image is not None:
            ih, iw = self.current_image.shape[:2]
            ex = max(0, min(ex, iw))
            ey = max(0, min(ey, ih))
        color = self.CLASS_COLORS.get(self.selected_class, '#ffffff')
        sx = self.start_x * self.zoom_scale + self.image_x
        sy = self.start_y * self.zoom_scale + self.image_y
        self.temp_box = self.canvas.create_rectangle(
            sx, sy,
            ex * self.zoom_scale + self.image_x,
            ey * self.zoom_scale + self.image_y,
            outline=color, width=2
        )

    # =========================================================================
    # CLOSE
    # =========================================================================

    def on_closing(self):
        if self.current_label_path:
            self.save_labels(force_save=True)
        save_config({'last_index': self.current_image_index})
        self.root.destroy()


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    root = tk.Tk()
    root.state('zoomed')
    YOLOLabelEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()