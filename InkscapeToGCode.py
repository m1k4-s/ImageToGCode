import numpy as np
from PIL import Image
from skimage import measure
import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.collections import LineCollection
import matplotlib.pyplot as plt
import os

# ---------------- CONFIGURATION ----------------
PAGE_WIDTH = 135   # mm
PAGE_HEIGHT = 210  # mm
FEED_RATE = 800    # mm/min
STEP = 0.5         # fill line spacing in mm
PEN_DOWN = "M3;S0"
PEN_UP = "M5;S180"

# ---------------- IMAGE HELPERS ----------------
def scale_image(img, max_width, max_height):
    w, h = img.size
    scale = min(max_width / w, max_height / h)
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

def pixel_to_mm(x, y, img_w, img_h, page_w, page_h):
    scale_x = page_w / img_w
    scale_y = page_h / img_h
    return x * scale_x, (img_h - y) * scale_y

# ---------------- FILL & OUTLINE GENERATION ----------------
def generate_outline(img_array):
    contours = measure.find_contours(1 - img_array, 0.5)
    lines = []
    for contour in contours:
        pts = [(p[1], p[0]) for p in contour]
        for i in range(len(pts) - 1):
            lines.append((pts[i], pts[i + 1]))
    return lines

def generate_fill_lines(img_array, spacing_px):
    height, width = img_array.shape
    lines = []
    step = max(1, int(spacing_px))
    for y in range(0, height, step):
        row = img_array[y, :]
        inside = False
        start_x = None
        for x in range(width):
            if row[x] < 0.5:
                if not inside:
                    inside = True
                    start_x = x
            else:
                if inside:
                    inside = False
                    lines.append(((start_x, y), (x - 1, y)))
        if inside:
            lines.append(((start_x, y), (width - 1, y)))
    return lines

# ---------------- PREVIEW ----------------
def show_preview(lines, width, height):
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.set_aspect('equal')
    ax.axis('off')
    lc = LineCollection(lines, colors='black', linewidths=0.5)
    ax.add_collection(lc)
    plt.title("Preview (Outline + Fill)")
    plt.tight_layout()
    plt.show()

# ---------------- G-CODE GENERATION ----------------
def generate_gcode(img, output_path):
    img_array = np.array(img.convert("L")) / 255.0
    spacing_px = max(1, int((STEP / PAGE_WIDTH) * img_array.shape[1]))

    outline_lines = generate_outline(img_array)
    fill_lines = generate_fill_lines(img_array, spacing_px)
    all_lines = outline_lines + fill_lines

    with open(output_path, "w") as f:
        f.write(f"; Image size: {img_array.shape[1]}x{img_array.shape[0]}\n")
        f.write("G21 ; set units to mm\n")
        f.write("G90 ; absolute positioning\n")
        for start, end in all_lines:
            x0, y0 = pixel_to_mm(start[0], start[1], img_array.shape[1], img_array.shape[0], PAGE_WIDTH, PAGE_HEIGHT)
            x1, y1 = pixel_to_mm(end[0], end[1], img_array.shape[1], img_array.shape[0], PAGE_WIDTH, PAGE_HEIGHT)
            f.write(f"G0 X{x0:.2f} Y{y0:.2f}\n")
            f.write(f"{PEN_DOWN}\n")
            f.write(f"G1 X{x1:.2f} Y{y1:.2f} F{FEED_RATE}\n")
            f.write(f"{PEN_UP}\n")

# ---------------- GUI ----------------
def select_image():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
    if not file_path:
        return

    try:
        img = Image.open(file_path).convert("L")
        preview_width = 200
        preview_height = int(preview_width * img.height / img.width)
        preview_img = img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
        preview_array = np.array(preview_img) / 255.0

        # Preview hatch/fill
        spacing_px = 1
        outline_lines = generate_outline(preview_array)
        fill_lines = generate_fill_lines(preview_array, spacing_px)
        all_lines = outline_lines + fill_lines
        show_preview(all_lines, preview_array.shape[1], preview_array.shape[0])

        # Save dialog
        output_file = filedialog.asksaveasfilename(defaultextension=".gcode",
                                                   filetypes=[("G-code files", "*.gcode")],
                                                   initialfile="output.gcode")
        if output_file:
            generate_gcode(img, output_file)
            messagebox.showinfo("Done!", f"G-code saved to:\n{output_file}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def build_gui():
    root = tk.Tk()
    root.title("dRawbot GCode-Generator")
    root.geometry("400x150")

    tk.Label(root, text="Wähle eine Bilddatei und generiere den GCode").pack(pady=10)
    tk.Button(root, text="Bilddatei wählen (.png, .jpg oder .jpeg)", command=select_image).pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    build_gui()
