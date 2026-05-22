import os
import random
import shutil

# ====== CONFIG ======
input_dir = r"C:\Users\surin\OneDrive\Skrivebord\yolo_training\dataset"
output_dir = r"C:\Users\surin\OneDrive\Skrivebord\yolo_training\dataset"

split_ratio = 0.9  # 90% train, 10% val

image_extensions = [".jpg", ".jpeg", ".png", ".bmp"]

# ====== CREATE FOLDERS ======
train_img_dir = os.path.join(output_dir, "images", "train")
val_img_dir   = os.path.join(output_dir, "images", "val")

train_lbl_dir = os.path.join(output_dir, "labels", "train")
val_lbl_dir   = os.path.join(output_dir, "labels", "val")

os.makedirs(train_img_dir, exist_ok=True)
os.makedirs(val_img_dir, exist_ok=True)
os.makedirs(train_lbl_dir, exist_ok=True)
os.makedirs(val_lbl_dir, exist_ok=True)

# ====== GET FILES ======
files = [f for f in os.listdir(input_dir)
         if os.path.splitext(f)[1].lower() in image_extensions]

random.shuffle(files)

split_index = int(len(files) * split_ratio)
train_files = files[:split_index]
val_files = files[split_index:]

def copy_pair(file_list, img_dest, lbl_dest):
    for img_file in file_list:
        name, ext = os.path.splitext(img_file)

        img_src = os.path.join(input_dir, img_file)
        lbl_src = os.path.join(input_dir, name + ".txt")

        if not os.path.exists(lbl_src):
            print(f"⚠️ Missing label for {img_file}, skipping")
            continue

        shutil.copy2(img_src, os.path.join(img_dest, img_file))
        shutil.copy2(lbl_src, os.path.join(lbl_dest, name + ".txt"))

# ====== COPY DATA ======
copy_pair(train_files, train_img_dir, train_lbl_dir)
copy_pair(val_files, val_img_dir, val_lbl_dir)

print("✅ Done splitting dataset!")
print(f"Train: {len(train_files)} images")
print(f"Val: {len(val_files)} images")