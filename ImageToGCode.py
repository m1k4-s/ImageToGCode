from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import tkinter as tk
from tkinter import filedialog, messagebox


# SETUP:

PAGE_WIDTH = 135     # may need to be reduced to 130mm
PAGE_HEIGHT = 210
FEED_RATE = 800      # may be increased
STEP = 0.5           # may be increased depending on pen width
PREVIEW_WIDTH = 300  # preview with matplotlib
PEN_DOWN = "M3;S0"   # depending on servo S40
PEN_UP = "M5;S180"   # depending on servo S140



def scale_image(img, max_width, max_height):
    w, h = img.size
    scale = min(max_width / w, max_height / h)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.Resampling.LANCZOS)

def generate_hatch_lines(img_array, spacing_px):
    lines = []
    height, width = img_array.shape
    max_offset = width + height
    for offset in np.arange(0, max_offset, spacing_px):
        line_points = []
        for x in range(width):
            y = int(offset - x)
            if 0 <= y < height:
                density = 1 - img_array[y, x]
                if density > 0.05:
                    line_points.append((x, y))
                else:
                    if len(line_points) > 1:
                        lines.append((line_points[0], line_points[-1]))
                    line_points = []
        if len(line_points) > 1:
            lines.append((line_points[0], line_points[-1]))
    return lines

def pixel_to_mm(x, y, img_width, img_height, page_width, page_height):
    scale_x = page_width / img_width
    scale_y = page_height / img_height
    return x * scale_x, y * scale_y

def show_hatch_preview(img_array, step_px=6):
    gray = img_array.astype(float)
    gray -= gray.min()
    if gray.max() > 0:
        gray /= gray.max()
    norm = gray

    height, width = img_array.shape
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.set_aspect('equal')
    ax.axis("off")

    segments = []
    for y in range(0, height, step_px):
        for x in range(0, width, step_px):
            density = 1 - norm[y, x]
            lines = max(1, int(1 + 3 * density))
            for i in range(lines):
                segments.append([(x, y + i), (x + step_px, y + i + step_px)])

    if segments:
        lc = LineCollection(segments, colors='black', linewidths=0.4, alpha=0.8)
        ax.add_collection(lc)

    edges = np.zeros_like(norm)
    edges[1:-1, 1:-1] = np.abs(norm[1:-1, 1:-1] - norm[0:-2, 1:-1]) + \
                        np.abs(norm[1:-1, 1:-1] - norm[1:-1, 0:-2])
    edge_coords = np.argwhere(edges > 0.05)
    for y, x in edge_coords:
        ax.plot([x, x+0.5], [y, y+0.5], color='black', linewidth=0.4)

    plt.title("Hatch Preview")
    plt.tight_layout()
    plt.show()

def generate_gcode(img, output_file):
    img = scale_image(img, PAGE_WIDTH, PAGE_HEIGHT)
    img_array = np.array(img)
    img_width, img_height = img.size

    lines = generate_hatch_lines(img_array / 255.0, spacing_px=STEP)

    with open(output_file, "w") as f:
        f.write("G21 ; set units to mm\n")
        f.write("G90 ; absolute positioning\n")
        for start, end in lines:
            x0, y0 = pixel_to_mm(start[0], start[1], img_width, img_height, PAGE_WIDTH, PAGE_HEIGHT)
            x1, y1 = pixel_to_mm(end[0], end[1], img_width, img_height, PAGE_WIDTH, PAGE_HEIGHT)
            f.write(f"G0 X{x0:.2f} Y{y0:.2f}\n")
            f.write(f"{PEN_DOWN}\n")
            f.write(f"G1 X{x1:.2f} Y{y1:.2f} F{FEED_RATE}\n")
            f.write(f"{PEN_UP}\n")


# GUI:


def select_image():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
    if file_path:
        img = Image.open(file_path).convert("L")
        preview_height = int(PREVIEW_WIDTH * img.height / img.width)
        preview_img = img.resize((PREVIEW_WIDTH, preview_height), Image.Resampling.LANCZOS)
        preview_array = np.array(preview_img)

        show_hatch_preview(preview_array)
        output_file = filedialog.asksaveasfilename(defaultextension=".gcode",
                                                   filetypes=[("G-code files", "*.gcode")],
                                                   initialfile="output.gcode")
        if output_file:
            generate_gcode(img, output_file)
            messagebox.showinfo("Yey, fertig!", f"G-code gespeichert: {output_file}")

root = tk.Tk()
root.title("dRawbot GCode-Generator")
root.geometry("400x150")

label = tk.Label(root, text="Wähle eine Bilddatei und generiere den GCode")
label.pack(pady=10)

btn_select = tk.Button(root, text="Bilddatei wählen (.png, .jpg oder .jpeg)", command=select_image)
btn_select.pack(pady=20)

root.mainloop()
