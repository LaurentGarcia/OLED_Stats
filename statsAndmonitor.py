#!/usr/bin/env python3
"""
Combined OLED Stats Display with Mode Switching for NAS

This script alternates every 30 seconds between two display modes:

Mode 0 (Scrolling Mode):
  - Line 0: Static IP address.
  - Line 1: "CPU: <load> | Temp: <temp>" scrolling horizontally if needed.
  - Line 2: "Mem: <mem>" scrolling horizontally if needed.
  - Line 3: "Disk: <disk>" scrolling horizontally if needed.

Mode 1 (Overview Mode):
  - A fixed layout optimized for NAS monitoring:
      Row 0: "IP: <IP>"
      Row 1: "CPU: <load> | Temp: <temp>"
      Row 2: "Mem: <mem>"
      Row 3: "Disk: <disk>"

Adjust the fonts and positions as needed.
"""

import time
import board
import busio
import gpiozero
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import subprocess

# ---------------------------
# Setup & Initialization
# ---------------------------
# Define the OLED reset pin (GPIO 4, active low)
oled_reset = gpiozero.OutputDevice(4, active_high=False)

# Display parameters
WIDTH = 128
HEIGHT = 64
LOOPTIME = 1.0        # Metric update interval in seconds
MODE_DURATION = 30    # Seconds per display mode

# I2C Setup
i2c = board.I2C()

# Manually reset the display (high -> low -> high for reset pulse)
oled_reset.on()
time.sleep(0.1)
oled_reset.off()
time.sleep(0.1)
oled_reset.on()

# Create the OLED display object (usually I2C address 0x3C)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)
oled.fill(0)
oled.show()

# Create an image buffer for drawing
image = Image.new('1', (WIDTH, HEIGHT))
draw = ImageDraw.Draw(image)

# Load fonts – adjust paths and sizes as desired.
try:
    # For both modes, we'll use the same main font.
    main_font = ImageFont.truetype('PixelOperator.ttf', 16)
except Exception as e:
    print("Error loading PixelOperator.ttf, using default font:", e)
    main_font = ImageFont.load_default()

# ---------------------------
# Helper Functions
# ---------------------------
def fetch_metrics():
    """Fetch system metrics and return them in a dictionary."""
    metrics = {}
    try:
        metrics['IP'] = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True).decode('utf-8').strip()
    except Exception:
        metrics['IP'] = "N/A"
    try:
        metrics['CPU'] = subprocess.check_output("top -bn1 | grep load | awk '{printf \"%.2f\", $(NF-2)}'", shell=True).decode('utf-8').strip()
    except Exception:
        metrics['CPU'] = "N/A"
    try:
        metrics['Temp'] = subprocess.check_output("vcgencmd measure_temp | cut -f2 -d'='", shell=True).decode('utf-8').strip()
    except Exception:
        metrics['Temp'] = "N/A"
    try:
        metrics['Mem'] = subprocess.check_output("free -m | awk 'NR==2{printf \"%.1f/%.1fGB %.0f%%\", $3/1024,$2/1024,($3/$2)*100}'", shell=True).decode('utf-8').strip()
    except Exception:
        metrics['Mem'] = "N/A"
    try:
        # Concatenate info for all disks (for all /dev entries)
        metrics['Disk'] = subprocess.check_output("df -h | awk '$1 ~ /^\\/dev/ {printf \"%s:%s(%s) \", $1, $3, $5}'", shell=True).decode('utf-8').strip()
    except Exception:
        metrics['Disk'] = "N/A"
    return metrics

def draw_scrolling_text_infinite(y, text, offset):
    """
    Draws text with infinite horizontal scrolling at vertical position y.
    Returns updated offset.
    """
    # Use textbbox to compute text width (instead of deprecated textsize)
    bbox = draw.textbbox((0, 0), text, font=main_font)
    text_width = bbox[2] - bbox[0]
    if text_width <= WIDTH:
        draw.text((0, y), text, font=main_font, fill=255)
        return 0
    spacing = 20  # Gap between repetitions
    total_length = text_width + spacing
    effective_offset = offset % total_length
    draw.text((-effective_offset, y), text, font=main_font, fill=255)
    # Draw a second instance if needed for seamless scrolling
    if text_width - effective_offset < WIDTH:
        draw.text((text_width - effective_offset + spacing, y), text, font=main_font, fill=255)
    return offset + 2  # Increase offset (adjust for scroll speed)

def display_scrolling_mode(metrics, offsets):
    """
    Display metrics in scrolling mode.
      - Line 0: "IP: <IP>" (static).
      - Line 1: "CPU: <load> | Temp: <temp>" (scrolls).
      - Line 2: "Mem: <mem>" (scrolls).
      - Line 3: "Disk: <disk>" (scrolls).
    Returns updated offsets.
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    # Static IP on line 0
    draw.text((0, 0), "IP: " + metrics['IP'], font=main_font, fill=255)
    # Scrolling text for other lines:
    cpu_text = "CPU: " + metrics['CPU'] + " | Temp: " + metrics['Temp']
    offsets['CPU'] = draw_scrolling_text_infinite(16, cpu_text, offsets['CPU'])
    offsets['Mem'] = draw_scrolling_text_infinite(32, "Mem: " + metrics['Mem'], offsets['Mem'])
    offsets['Disk'] = draw_scrolling_text_infinite(48, "Disk: " + metrics['Disk'], offsets['Disk'])
    oled.image(image)
    oled.show()
    return offsets

def display_overview_mode(metrics):
    """
    Display metrics in a fixed (overview) layout using a larger, clear format.
    Layout (each row uses main_font at 16):
      Row 0 (y=0): "IP: <IP>"
      Row 1 (y=16): "CPU: <load> | Temp: <temp>"
      Row 2 (y=32): "Mem: <mem>"
      Row 3 (y=48): "Disk: <disk>"

    If a line is too long, it will be drawn as-is (or you could add logic to truncate).
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    draw.text((0, 0), "IP: " + metrics['IP'], font=main_font, fill=255)
    draw.text((0, 16), "CPU: " + metrics['CPU'] + " | Temp: " + metrics['Temp'], font=main_font, fill=255)
    draw.text((0, 32), "Mem: " + metrics['Mem'], font=main_font, fill=255)
    draw.text((0, 48), "Disk: " + metrics['Disk'], font=main_font, fill=255)
    oled.image(image)
    oled.show()

# ---------------------------
# Main Loop with Mode Switching
# ---------------------------
# Offsets for scrolling mode
offsets = {'CPU': 0, 'Mem': 0, 'Disk': 0}
current_mode = 0  # 0 = scrolling mode, 1 = overview (fixed layout) mode
mode_start_time = time.time()

while True:
    # Toggle display mode every MODE_DURATION seconds
    if time.time() - mode_start_time >= MODE_DURATION:
        current_mode = 1 - current_mode  # Toggle between 0 and 1
        mode_start_time = time.time()

    # Fetch the latest metrics
    metrics = fetch_metrics()

    if current_mode == 0:
        # Scrolling mode: update more frequently for smooth animation
        offsets = display_scrolling_mode(metrics, offsets)
        time.sleep(0.1)
    else:
        # Overview mode: update once per LOOPTIME
        display_overview_mode(metrics)
        time.sleep(LOOPTIME)
