from PIL import Image
import numpy as np


INPUT_IMAGE = "input.jpg"       # Path to your input image
OUTPUT_GCODE = "output.gcode"   # Path for G-code output
PAGE_WIDTH = 148                # A5 width in mm
PAGE_HEIGHT = 210               # A5 height in mm
FEED_RATE = 800                 # mm/min
HATCH_ANGLE = 45                # degrees
DENSE_SPACING = 0.5             # spacing for darkest gray in mm
NUM_GRAY_LEVELS = 4             # number of hatch levels

# Pen commands
PEN_DOWN = "M3:S0"
PEN_UP = "M5;S180"



def scale_image(img, max_width, max_height):
    """Scale image to fit within max_width x max_height while keeping aspect ratio"""
    w, h = img.size
    scale = min(max_width / w, max_height / h)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def generate_hatch_lines(img_array, spacing, gray_threshold):
    """Generate hatch lines as list of segments [(x0,y0,x1,y1), ...]"""
    lines = []
    height, width = img_array.shape
    # Diagonal lines: iterate over offsets along the top and left edges
    max_offset = width + height
    for offset in np.arange(0, max_offset, spacing):
        line_segments = []
        for x in range(width):
            y = int(offset - x)
            if 0 <= y < height:
                if img_array[y, x] < gray_threshold:
                    line_segments.append((x, y))
                else:
                    if len(line_segments) > 1:
                        # Create segment from first to last point
                        lines.append((line_segments[0], line_segments[-1]))
                    line_segments = []
        if len(line_segments) > 1:
            lines.append((line_segments[0], line_segments[-1]))
    return lines

def pixel_to_mm(x, y, img_width, img_height, page_width, page_height):
    """Convert pixel coordinates to mm coordinates on page"""
    scale_x = page_width / img_width
    scale_y = page_height / img_height
    return x * scale_x, y * scale_y

# ==========================
# MAIN SCRIPT
# ==========================

# Load image and convert to grayscale
img = Image.open(INPUT_IMAGE).convert("L")
img = scale_image(img, PAGE_WIDTH, PAGE_HEIGHT)
img_array = np.array(img)

img_width, img_height = img.size

# Define gray thresholds and hatch spacing for each level
gray_thresholds = [64, 128, 192, 256]  # 0-63 darkest, etc.
spacing_levels = [DENSE_SPACING * i for i in range(1, NUM_GRAY_LEVELS+1)]

# Open G-code file
with open(OUTPUT_GCODE, "w") as f:
    f.write(f"G21 ; set units to mm\n")
    f.write(f"G90 ; absolute positioning\n")

    # Loop over each gray level
    for gray_idx in range(NUM_GRAY_LEVELS):
        spacing = spacing_levels[gray_idx]
        threshold = gray_thresholds[gray_idx]
        lines = generate_hatch_lines(img_array, spacing, threshold)

        for (start, end) in lines:
            x0, y0 = pixel_to_mm(start[0], start[1], img_width, img_height, PAGE_WIDTH, PAGE_HEIGHT)
            x1, y1 = pixel_to_mm(end[0], end[1], img_width, img_height, PAGE_WIDTH, PAGE_HEIGHT)

            # Move to start
            f.write(f"G0 X{x0:.2f} Y{y0:.2f}\n")
            f.write(f"{PEN_DOWN}\n")
            # Draw line
            f.write(f"G1 X{x1:.2f} Y{y1:.2f} F{FEED_RATE}\n")
            f.write(f"{PEN_UP}\n")

print(f"G-code saved to {OUTPUT_GCODE}")
