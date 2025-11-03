from PIL import Image
import numpy as np
import matplotlib.pyplot as plt

# ==========================
# CONFIGURATION
# ==========================
INPUT_IMAGE = "input.jpg"       # Input image file
OUTPUT_GCODE = "output.gcode"   # Output G-code file
PAGE_WIDTH = 148                # A5 width in mm
PAGE_HEIGHT = 210               # A5 height in mm
FEED_RATE = 800                 # mm/min
DENSE_SPACING = 0.5             # mm for darkest level
NUM_GRAY_LEVELS = 4             # number of shading bands

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

def show_hatch_preview(img_array):
    """Display a readable preview of hatch shading."""
    height, width = img_array.shape
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.imshow(np.ones_like(img_array) * 255, cmap='gray')

    # normalize to 0–1
    norm = (img_array - img_array.min()) / (img_array.max() - img_array.min() + 1e-6)

    # invert so dark = 1, light = 0 (easier to think in density)
    norm = 1.0 - norm

    # divide into discrete tone bands
    levels = np.linspace(0, 1, NUM_GRAY_LEVELS + 1)
    preview_spacing = np.linspace(14, 4, NUM_GRAY_LEVELS, dtype=int)  # lighter→darker

    for i in range(NUM_GRAY_LEVELS):
        # pixels in this band only
        mask = (norm >= levels[i]) & (norm < levels[i + 1])
        spacing = preview_spacing[i]

        # draw short diagonal hatch marks sparsely
        ys, xs = np.nonzero(mask[::spacing, ::spacing])
        for y, x in zip(ys * spacing, xs * spacing):
            ax.plot([x, x + spacing], [y, y + spacing],
                    color='black', linewidth=0.4, alpha=0.8)

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.set_aspect('equal')
    ax.set_axis_off()
    plt.title("Hatch Preview")
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

# thresholds for G-code hatching
gray_thresholds = [64, 128, 192, 256]
spacing_levels = [DENSE_SPACING * (i + 1) for i in range(NUM_GRAY_LEVELS)]

# --- PREVIEW ---
print("Generating preview...")
preview_width = 400
preview_height = int(preview_width * img_height / img_width)
preview_img = img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
preview_array = np.array(preview_img)
show_hatch_preview(preview_array)

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

print(f"\n✅ Done! G-code saved to: {OUTPUT_GCODE}")
