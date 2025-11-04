import numpy as np
from PIL import Image
from skimage import measure
import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.collections import LineCollection
import matplotlib.pyplot as plt
import os

# ---------------- CONFIG ----------------
MAX_WIDTH_MM = 135.0    # maximum printed width in mm (strict)
MAX_HEIGHT_MM = 210.0   # maximum printed height in mm
FEED_RATE = 2000
STEP = 0.35              # hatch spacing in mm
PEN_DOWN = "M3;S0"
PEN_UP = "M5;S180"
PREVIEW_WIDTH = 300      # preview width in pixels
SKIP_TINY_MOVE_MM = 0.01 # skip moves shorter than this in mm

# ---------------- HELPERS ----------------

def scale_and_rotate_image_to_mm(img, max_w_mm, max_h_mm):
    """
    Rotate to portrait if needed, then scale preserving aspect ratio so
    printed width <= max_w_mm and printed height <= max_h_mm.
    Returns the scaled image (pixels) and its printed size in mm.
    """
    w, h = img.size
    # rotate to portrait if image is wider than tall and page is portrait
    if w > h and max_w_mm < max_h_mm:
        img = img.rotate(90, expand=True)
        w, h = img.size

    # We'll choose a pixel scale such that final pixel dimensions map to mm simply:
    # compute scale factor in *mm per pixel* from image pixels -> mm limits
    # We want to preserve aspect ratio and fit within max mm box.
    scale_factor = min(max_w_mm / w, max_h_mm / h)  # mm per pixel if we interpret pixel as 1 unit
    # But this scale_factor gives mm per pixel < 1 usually. We'll keep pixel grid as-is;
    # printed size (mm) = pixel_count * scale_factor.
    printed_w_mm = w * scale_factor
    printed_h_mm = h * scale_factor

    # No change to pixel count — we keep the image resolution (w,h) but track mm size.
    # (We could resample image to reduce pixel count for performance, but keep full for quality.)
    return img, printed_w_mm, printed_h_mm, scale_factor

def pixel_to_mm(x, y, img_w_px, img_h_px, printed_w_mm, printed_h_mm):
    """Map a pixel coordinate to mm within the printed area. Flip Y so origin is bottom-left."""
    sx = printed_w_mm / img_w_px
    sy = printed_h_mm / img_h_px
    return x * sx, (img_h_px - y) * sy

# ---------------- LINE GENERATION ----------------

def generate_outline(img_array):
    """Return list of line segments from contours. img_array normalized 0..1 (white..black)."""
    contours = measure.find_contours(1 - img_array, 0.5)
    lines = []
    for contour in contours:
        pts = [(p[1], p[0]) for p in contour]  # contour gives (row,col) -> (y,x)
        # turn contour polyline into segments
        for i in range(len(pts) - 1):
            lines.append((pts[i], pts[i + 1]))
    return lines

def generate_fill_lines_bw(img_array, spacing_px):
    """Black & white fill: merge horizontal runs into segments. spacing_px is vertical step in pixels."""
    height, width = img_array.shape
    lines = []
    step = max(1, int(spacing_px))
    for y in range(0, height, step):
        row = img_array[y, :]
        inside = False
        start_x = 0
        for x in range(width):
            is_black = row[x] < 0.5
            if is_black and not inside:
                inside = True
                start_x = x
            elif (not is_black) and inside:
                inside = False
                lines.append(((start_x, y), (x - 1, y)))
        if inside:
            lines.append(((start_x, y), (width - 1, y)))
    return lines

def generate_density_hatch_blocks(img_array, step_px, max_lines_per_block=4, diagonal=False, block_size=4):
    """
    Greyscale hatch using averaged blocks to reduce density.
    step_px = pixel spacing (vertical) for blocks.
    block_size = pixels used to compute average darkness.
    """
    h, w = img_array.shape
    lines = []
    step = max(1, int(step_px))
    bs = max(1, int(block_size))
    for y in range(0, h, step):
        for x in range(0, w, step):
            block = img_array[y:y+bs, x:x+bs]
            if block.size == 0:
                continue
            avg = 1.0 - float(np.mean(block))  # 0..1 blackness
            num = int(round(avg * max_lines_per_block))
            if num <= 0:
                continue
            for i in range(num):
                offset = (i + 0.5) * (bs / max_lines_per_block)  # center within block
                if diagonal:
                    lines.append(((x, y + offset), (x + step, y + offset + step)))
                else:
                    lines.append(((x, y + offset), (x + step, y + offset)))
    # Optional: we could merge adjacent colinear segments here — keep simple for now.
    return lines

# ---------------- PREVIEW ----------------

def show_preview(lines, width_px, height_px):
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.set_xlim(0, width_px)
    ax.set_ylim(height_px, 0)
    ax.set_aspect('equal')
    ax.axis('off')
    if lines:
        lc = LineCollection(lines, colors='black', linewidths=0.5)
        ax.add_collection(lc)
    plt.title("Preview")
    plt.tight_layout()
    plt.show()

# ---------------- GCODE OUTPUT ----------------

def generate_gcode(img_px, lines_px, output_path, printed_w_mm, printed_h_mm):
    img_w_px, img_h_px = img_px.size
    sx = printed_w_mm / img_w_px
    sy = printed_h_mm / img_h_px
    with open(output_path, "w") as f:
        f.write(f"; Image size (scaled): {printed_w_mm:.2f} x {printed_h_mm:.2f} mm ({img_w_px}x{img_h_px} px)\n")
        f.write("G21 ; mm units\nG90 ; absolute positioning\n")
        last_pos = None
        for (sx0, sy0), (sx1, sy1) in lines_px:
            x0, y0 = pixel_to_mm(sx0, sy0, img_w_px, img_h_px, printed_w_mm, printed_h_mm)
            x1, y1 = pixel_to_mm(sx1, sy1, img_w_px, img_h_px, printed_w_mm, printed_h_mm)
            # skip micro-moves
            if abs(x1 - x0) < SKIP_TINY_MOVE_MM and abs(y1 - y0) < SKIP_TINY_MOVE_MM:
                continue
            # rapid to start
            if last_pos != (round(x0,3), round(y0,3)):
                f.write(f"G0 X{x0:.2f} Y{y0:.2f}\n")
            f.write(f"{PEN_DOWN}\n")
            f.write(f"G1 X{x1:.2f} Y{y1:.2f} F{FEED_RATE}\n")
            f.write(f"{PEN_UP}\n")
            last_pos = (round(x1,3), round(y1,3))

# ---------------- GUI / MAIN FLOW ----------------

def select_image():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
    if not file_path:
        return
    try:
        img_orig = Image.open(file_path).convert("L")

        # 1) rotate to portrait if needed and compute printed mm size (no pixel resampling)
        w_px, h_px = img_orig.size
        img_work = img_orig
        if w_px > h_px:
            img_work = img_orig.rotate(90, expand=True)
        img_w_px, img_h_px = img_work.size

        scale_mm_per_px = min(MAX_WIDTH_MM / img_w_px, MAX_HEIGHT_MM / img_h_px)
        printed_w_mm = img_w_px * scale_mm_per_px
        printed_h_mm = img_h_px * scale_mm_per_px

        # 2) For preview, make a downsampled copy (keeps aspect)
        preview_h = int(PREVIEW_WIDTH * img_h_px / img_w_px)
        preview_img = img_work.resize((PREVIEW_WIDTH, preview_h), Image.Resampling.LANCZOS)
        preview_arr = np.array(preview_img) / 255.0

        # 3) Compute spacing in pixels for full-size image (so STEP mm -> spacing_px)
        spacing_px_full = max(1, int(round(STEP / scale_mm_per_px)))  # STEP mm -> pixels
        # For preview preview spacing (scale down)
        spacing_px_preview = max(1, int(round(spacing_px_full * (PREVIEW_WIDTH / img_w_px))))

        # 4) Build preview lines (fast, from preview image)
        preview_lines = []
        if outline_var.get():
            preview_lines += generate_outline(preview_arr)
        hatch_choice = hatch_var.get()
        if hatch_choice == "Black & White Fill":
            preview_lines += generate_fill_lines_bw(preview_arr, spacing_px_preview)
        elif hatch_choice == "Greyscale Horizontal":
            preview_lines += generate_density_hatch_blocks(preview_arr, spacing_px_preview, max_lines_per_block=4, diagonal=False, block_size=4)
        elif hatch_choice == "Greyscale Diagonal":
            preview_lines += generate_density_hatch_blocks(preview_arr, spacing_px_preview, max_lines_per_block=4, diagonal=True, block_size=4)

        show_preview(preview_lines, preview_arr.shape[1], preview_arr.shape[0])

        # 5) Build full-size lines from img_work (the same image used for G-code)
        img_work_arr = np.array(img_work) / 255.0
        full_lines = []
        if outline_var.get():
            full_lines += generate_outline(img_work_arr)
        if hatch_choice == "Black & White Fill":
            full_lines += generate_fill_lines_bw(img_work_arr, spacing_px_full)
        elif hatch_choice == "Greyscale Horizontal":
            full_lines += generate_density_hatch_blocks(img_work_arr, spacing_px_full, max_lines_per_block=4, diagonal=False, block_size=4)
        elif hatch_choice == "Greyscale Diagonal":
            full_lines += generate_density_hatch_blocks(img_work_arr, spacing_px_full, max_lines_per_block=4, diagonal=True, block_size=4)

        # 6) Save G-code using true printed mm size
        out = filedialog.asksaveasfilename(defaultextension=".gcode", filetypes=[("G-code files", "*.gcode")], initialfile="output.gcode")
        if out:
            # ensure folder exists
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            generate_gcode(img_work, full_lines, out, printed_w_mm, printed_h_mm)
            messagebox.showinfo("Done", f"G-code saved to:\n{out}\nPrinted size: {printed_w_mm:.2f} x {printed_h_mm:.2f} mm")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# ---------------- GUI ----------------
root = tk.Tk()
root.title("dRawbot GCode-Generator")
root.geometry("460x240")

tk.Label(root, text="Select an image and generate G-code", font=("Arial", 12, "bold")).pack(pady=6)
outline_var = tk.BooleanVar(value=True)
tk.Checkbutton(root, text="Draw Outline", variable=outline_var).pack()

hatch_var = tk.StringVar(value="Black & White Fill")
tk.Label(root, text="Hatch Type:").pack()
tk.OptionMenu(root, hatch_var, "Black & White Fill", "Greyscale Horizontal", "Greyscale Diagonal").pack(pady=6)

tk.Button(root, text="Select Image & Generate", command=select_image, width=36).pack(pady=12)

root.mainloop()
