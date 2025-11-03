from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

# ==========================
# CONFIGURATION
# ==========================
INPUT_IMAGE = "input.jpg"       # Input image file
OUTPUT_GCODE = "output.gcode"   # Output G-code file
PAGE_WIDTH = 148                # A5 width in mm
PAGE_HEIGHT = 210               # A5 height in mm
FEED_RATE = 800                 # mm/min
DENSE_SPACING = 0.5             # mm for darkest level
NUM_GRAY_LEVELS = 4             # number of shading bands for G-code

# Pen macros
PEN_DOWN = "M3;S0"
PEN_UP = "M5;S180"

# ==========================
# HELPER FUNCTIONS
# ==========================

def scale_image(img, max_width, max_height):
    """Scale image to fit within max_width x max_height while keeping aspect ratio."""
    w, h = img.size
    scale = min(max_width / w, max_height / h)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.Resampling.LANCZOS)

def generate_hatch_lines(img_array, spacing, gray_threshold):
    """Generate diagonal hatch lines based on grayscale threshold."""
    lines = []
    height, width = img_array.shape
    max_offset = width + height
    for offset in np.arange(0, max_offset, spacing):
        line_points = []
        for x in range(width):
            y = int(offset - x)
            if 0 <= y < height:
                if img_array[y, x] < gray_threshold:
                    line_points.append((x, y))
                else:
                    if len(line_points) > 1:
                        lines.append((line_points[0], line_points[-1]))
                    line_points = []
        if len(line_points) > 1:
            lines.append((line_points[0], line_points[-1]))
    return lines

def pixel_to_mm(x, y, img_width, img_height, page_width, page_height):
    """Convert pixel coordinates to mm on page."""
    scale_x = page_width / img_width
    scale_y = page_height / img_height
    return x * scale_x, y * scale_y

def show_hatch_preview(img_array, step=6):
    """Preview with single diagonal hatching plus outlines."""
    # Normalize image to 0-1
    gray = img_array.astype(float)
    gray -= gray.min()
    if gray.max() > 0:
        gray /= gray.max()
    norm = 1 - gray  # invert: dark = higher density

    height, width = img_array.shape
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.set_aspect('equal')
    ax.axis("off")

    # --- Hatch lines ---
    segments = []
    for y in range(0, height, step):
        for x in range(0, width, step):
            density = norm[y, x]
            lines = int(1 + 3 * density)  # 1–4 lines
            for i in range(lines):
                segments.append([(x, y + i), (x + step, y + i + step)])  # only main diagonal

    if len(segments) > 0:
        lc = LineCollection(segments, colors='black', linewidths=0.4, alpha=0.8)
        ax.add_collection(lc)

    # --- Outline detection ---
    edges = np.zeros_like(norm)
    edges[1:-1, 1:-1] = np.abs(norm[1:-1, 1:-1] - norm[0:-2, 1:-1]) + \
                        np.abs(norm[1:-1, 1:-1] - norm[1:-1, 0:-2])
    edge_coords = np.argwhere(edges > 0.1)  # sensitivity threshold

    for y, x in edge_coords:
        ax.plot([x, x+1], [y, y+1], color='black', linewidth=0.5)

    plt.title("Hatch Preview with Outlines")
    plt.tight_layout()
    plt.show()

# ==========================
# MAIN SCRIPT
# ==========================

print("Loading image...")
img = Image.open(INPUT_IMAGE).convert("L")
img = scale_image(img, PAGE_WIDTH, PAGE_HEIGHT)
img_array = np.array(img)
img_width, img_height = img.size
print(f"Image loaded: {img_width}x{img_height}")

# G-code parameters
gray_thresholds = [64, 128, 192, 256]
spacing_levels = [DENSE_SPACING * (i + 1) for i in range(NUM_GRAY_LEVELS)]

# --- PREVIEW ---
print("Generating preview...")
preview_width = 300  # smaller = faster
preview_height = int(preview_width * img_height / img_width)
preview_img = img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
preview_array = np.array(preview_img)
show_hatch_preview(preview_array, step=6)

# --- G-CODE GENERATION ---
print("Generating G-code...")
with open(OUTPUT_GCODE, "w") as f:
    f.write("G21 ; set units to mm\n")
    f.write("G90 ; absolute positioning\n")

    for gray_idx in range(NUM_GRAY_LEVELS):
        threshold = gray_thresholds[gray_idx]
        spacing_mm = spacing_levels[gray_idx]
        lines = generate_hatch_lines(img_array, spacing_mm, threshold)

        for start, end in lines:
            x0, y0 = pixel_to_mm(start[0], start[1], img_width, img_height,
                                 PAGE_WIDTH, PAGE_HEIGHT)
            x1, y1 = pixel_to_mm(end[0], end[1], img_width, img_height,
                                 PAGE_WIDTH, PAGE_HEIGHT)
            f.write(f"G0 X{x0:.2f} Y{y0:.2f}\n")
            f.write(f"{PEN_DOWN}\n")
            f.write(f"G1 X{x1:.2f} Y{y1:.2f} F{FEED_RATE}\n")
            f.write(f"{PEN_UP}\n")

print(f" G-code saved to: {OUTPUT_GCODE}")
