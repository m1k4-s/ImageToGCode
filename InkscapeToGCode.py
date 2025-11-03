import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from skimage import measure
import tkinter as tk
from tkinter import filedialog, messagebox
import os

# ---------------- CONFIGURATION ----------------
PAGE_WIDTH = 135        # mm
PAGE_HEIGHT = 210       # mm
FEED_RATE = 800         # mm/min
STEP = 0.5              # fill line spacing in mm
PEN_DOWN = "M3;S0"
PEN_UP = "M5;S180"

# ---------------- IMAGE HELPERS ----------------
def scale_image(img, max_width, max_height):
    """Scale image to fit within max_width x max_height while keeping aspect ratio."""
    w, h = img.size
    scale = min(max_width / w, max_height / h)
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

def pixel_to_mm(x, y, img_w, img_h, page_w, page_h):
    """Convert pixel coordinates to mm on page, flipping Y for plotter orientation."""
    scale_x = page_w / img_w
    scale_y = page_h / img_h
    return x * scale_x, (img_h - y) * scale_y

# ---------------- OUTLINE ----------------
def generate_outline(img_array):
    """Generate continuous outline lines using contours."""
    contours = measure.find_contours(1 - img_array, 0.5)
    lines = []
    for contour in contours:
        pts = [(p[1], p[0]) for p in contour]  # x,y swap
        for i in range(len(pts) - 1):
            lines.append((pts[i], pts[i + 1]))
    return lines

# ---------------- FILL ----------------
def generate_fill_lines(img_array, step_mm, page_w, page_h):
    """Generate travel-optimized fill lines using boustrophedon scanning."""
    height, width = img_array.shape
    lines = []

    step_px = max(1, int(step_mm / page_w * width))  # mm -> pixels

    for row_idx, y in enumerate(range(0, height, step_px)):
        row = img_array[y, :]
        start = None

        # Determine scanning direction for this row
        if row_idx % 2 == 0:
            x_range = range(width)
        else:
            x_range = range(width - 1, -1, -1)

        for x in x_range:
            if row[x] < 0.5:  # black pixel
                if start is None:
                    start = x
            else:
                if start is not None:
                    lines.append(((start, y), (x - 1, y)))
                    start = None

        if start is not None:
            # End of row
            end_x = x_range[-1]
            lines.append(((start, y), (end_x, y)))

    return lines


# ---------------- PREVIEW ----------------
def show_preview(lines, width, height):
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)  # flip Y for image-style preview
    ax.set_aspect('equal')
    ax.axis('off')

    lc = LineCollection(lines, colors='black', linewidths=0.5)
    ax.add_collection(lc)
    plt.title("Preview (Outline + Fill)")
    plt.tight_layout()
    plt.show()

# ---------------- G-CODE GENERATION ----------------
def generate_gcode(lines, img_w, img_h, out_path):
    with open(out_path, "w") as f:
        f.write("G21 ; set units to mm\n")
        f.write("G90 ; absolute positioning\n")
        for start, end in lines:
            x0, y0 = pixel_to_mm(start[0], start[1], img_w, img_h, PAGE_WIDTH, PAGE_HEIGHT)
            x1, y1 = pixel_to_mm(end[0], end[1], img_w, img_h, PAGE_WIDTH, PAGE_HEIGHT)
            f.write(f"G0 X{x0:.2f} Y{y0:.2f}\n")
            f.write(f"{PEN_DOWN}\n")
            f.write(f"G1 X{x1:.2f} Y{y1:.2f} F{FEED_RATE}\n")
            f.write(f"{PEN_UP}\n")

# ---------------- MAIN PROCESS ----------------
def process_image(image_path):
    img = Image.open(image_path).convert("L")
    img = scale_image(img, PAGE_WIDTH * 10, PAGE_HEIGHT * 10)
    img_array = np.array(img) / 255.0

    # Generate outline
    outline_lines = generate_outline(img_array)
    
    # Generate fill
    fill_lines = generate_fill_lines(img_array, STEP, PAGE_WIDTH, PAGE_HEIGHT)

    all_lines = outline_lines + fill_lines

    # Preview
    show_preview(all_lines, img_array.shape[1], img_array.shape[0])

    # Save G-code
    output_path = os.path.splitext(image_path)[0] + "_fill.gcode"
    generate_gcode(all_lines, img_array.shape[1], img_array.shape[0], output_path)
    messagebox.showinfo("Done!", f"G-code saved to:\n{output_path}")

# ---------------- GUI ----------------


PREVIEW_WIDTH = 300  # for preview scaling

# ==========================
# PLACEHOLDER FUNCTIONS
# ==========================
# Replace these with your optimized fill + outline generation
def show_hatch_preview(img_array):
    # Just a placeholder to show a simple preview
    import matplotlib.pyplot as plt
    plt.imshow(img_array, cmap='gray')
    plt.title("Preview")
    plt.axis('off')
    plt.show()

def generate_gcode(img, output_path):
    # Placeholder function to generate G-code
    # Replace with your optimized generator
    w, h = img.size
    with open(output_path, "w") as f:
        f.write("; G-code placeholder\n")
        f.write(f"; Image size: {w}x{h}\n")
        f.write("G21 ; set units to mm\nG90 ; absolute positioning\n")
    print(f"G-code written to {output_path}")

# ==========================
# GUI FUNCTION
# ==========================
def select_image():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
    if not file_path:
        return

    img = Image.open(file_path).convert("L")
    preview_height = int(PREVIEW_WIDTH * img.height / img.width)
    preview_img = img.resize((PREVIEW_WIDTH, preview_height), Image.Resampling.LANCZOS)
    preview_array = np.array(preview_img)

    # Show preview
    show_hatch_preview(preview_array)

    # Ask user where to save
    output_file = filedialog.asksaveasfilename(defaultextension=".gcode",
                                               filetypes=[("G-code files", "*.gcode")],
                                               initialfile="output.gcode")
    if output_file:
        generate_gcode(img, output_file)
        messagebox.showinfo("Fertig!", f"G-code gespeichert:\n{output_file}")

# ==========================
# MAIN GUI
# ==========================
root = tk.Tk()
root.title("dRawbot GCode-Generator")
root.geometry("400x150")

label = tk.Label(root, text="Wähle eine Bilddatei und generiere den GCode")
label.pack(pady=10)

btn_select = tk.Button(root, text="Bilddatei wählen (.png, .jpg oder .jpeg)", command=select_image)
btn_select.pack(pady=20)

root.mainloop()
