#!/usr/bin/env python3
"""
Combined OLED Stats Display with Mode Switching for NAS Disk Overview

This script alternates every 30 seconds between two display modes:

Mode 0 (Scrolling Mode):
  - Line 0: "IP: <IP>" (static).
  - Line 1: "CPU: <load> | Temp: <temp>" (scrolls if needed).
  - Line 2: "Mem: <mem>" (scrolls if needed).
  - Line 3: "Disk: <disk>" (scrolls if needed; all disk info concatenated).

Mode 1 (Disk Overview Mode):
  - A header "Disk Usage:" is centered on row 0.
  - Up to three lines (rows 1, 2, and 3) display one disk each (if available).
    Each disk line scrolls horizontally if too long.

Adjust fonts, scroll speeds, and positions as needed.
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
LOOPTIME = 1.0        # Metric update interval (seconds)
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

# Load main font (using PixelOperator.ttf at size 16)
try:
    main_font = ImageFont.truetype('PixelOperator.ttf', 16)
except Exception as e:
    print("Error loading PixelOperator.ttf, using default font:", e)
    main_font = ImageFont.load_default()

# ---------------------------
# Helper Functions
# ---------------------------
def fetch_metrics():
    """Fetch system metrics and return them in a dictionary.
       For disk info, split each disk line into a list.
    """
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
        # Produce one disk per line. For each disk (lines starting with /dev), output: "dev:used(perc)"
        raw_disk = subprocess.check_output(
            "df -h | awk '$1 ~ /^\\/dev/ {printf \"%s:%s(%s)\\n\", $1, $3, $5}'",
            shell=True).decode('utf-8').strip()
        disk_lines = raw_disk.splitlines()
        if disk_lines:
            metrics['Disk'] = disk_lines
        else:
            metrics['Disk'] = ["N/A"]
    except Exception:
        metrics['Disk'] = ["N/A"]
    return metrics

def draw_scrolling_text_infinite(y, text, offset, font=main_font):
    """
    Draws text with infinite horizontal scrolling at vertical position y.
    Returns updated offset.
    """
    # Use textbbox to compute text width (instead of deprecated textsize)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    if text_width <= WIDTH:
        draw.text((0, y), text, font=font, fill=255)
        return 0
    spacing = 20  # Gap between repetitions
    total_length = text_width + spacing
    effective_offset = offset % total_length
    draw.text((-effective_offset, y), text, font=font, fill=255)
    if text_width - effective_offset < WIDTH:
        draw.text((text_width - effective_offset + spacing, y), text, font=font, fill=255)
    return offset + 2  # Increase offset (adjust for scroll speed)

def display_scrolling_mode(metrics, offsets):
    """
    Display metrics in scrolling mode:
      - Line 0: "IP: <IP>" (static).
      - Line 1: "CPU: <load> | Temp: <temp>" (scrolls).
      - Line 2: "Mem: <mem>" (scrolls).
      - Line 3: "Disk: <disk>" (scrolls; concatenated).
    Returns updated offsets.
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    draw.text((0, 0), "IP: " + metrics['IP'], font=main_font, fill=255)
    cpu_text = "CPU: " + metrics['CPU'] + " | Temp: " + metrics['Temp']
    offsets['CPU'] = draw_scrolling_text_infinite(16, cpu_text, offsets['CPU'])
    offsets['Mem'] = draw_scrolling_text_infinite(32, "Mem: " + metrics['Mem'], offsets['Mem'])
    # For Mode 0, concatenate all disk lines into one string.
    disk_concat = " ".join(metrics['Disk'])
    offsets['Disk'] = draw_scrolling_text_infinite(48, "Disk: " + disk_concat, offsets['Disk'])
    oled.image(image)
    oled.show()
    return offsets

def display_disk_overview_mode(metrics, disk_offsets):
    """
    Display Disk Overview Mode:
      - Row 0: Centered header "Disk Usage:"
      - Rows 1 to 3: Each row displays one disk's info (if available), scrolling horizontally.
    The disk info is taken from metrics['Disk'] (a list of disk lines).
    Uses a dictionary disk_offsets for independent horizontal scrolling per disk.
    Returns updated disk_offsets.
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    # Header centered on row 0
    header = "Disk Usage:"
    header_bbox = draw.textbbox((0, 0), header, font=main_font)
    header_width = header_bbox[2] - header_bbox[0]
    header_x = (WIDTH - header_width) // 2
    draw.text((header_x, 0), header, font=main_font, fill=255)

    disk_lines = metrics.get('Disk', ["N/A"])
    # We'll display up to 3 disks (rows 1, 2, and 3 at y=16, 32, 48)
    for i in range(min(3, len(disk_lines))):
        y = 16 + i * 16
        # Use the corresponding offset for this disk line
        disk_offsets[i] = draw_scrolling_text_infinite(y, disk_lines[i], disk_offsets.get(i, 0), font=main_font)
    oled.image(image)
    oled.show()
    return disk_offsets

# ---------------------------
# Main Loop with Mode Switching
# ---------------------------
# Offsets for Mode 0 scrolling (for CPU, Mem, Disk concatenated)
offsets = {'CPU': 0, 'Mem': 0, 'Disk': 0}
# Offsets for Disk Overview Mode (one per disk line)
disk_overview_offsets = {0: 0, 1: 0, 2: 0}
current_mode = 0  # 0 = scrolling mode (all metrics), 1 = disk overview mode
mode_start_time = time.time()
last_update = time.time()
metrics = fetch_metrics()  # initial metrics

while True:
    # Switch display mode every MODE_DURATION seconds
    if time.time() - mode_start_time >= MODE_DURATION:
        current_mode = 1 - current_mode  # Toggle mode
        mode_start_time = time.time()

    # Update metrics every LOOPTIME seconds
    if time.time() - last_update >= LOOPTIME:
        metrics = fetch_metrics()
        last_update = time.time()

    if current_mode == 0:
        # Mode 0: Scrolling mode (all metrics)
        offsets = display_scrolling_mode(metrics, offsets)
        time.sleep(0.1)
    else:
        # Mode 1: Disk Overview Mode (each disk on its own line)
        disk_overview_offsets = display_disk_overview_mode(metrics, disk_overview_offsets)
        time.sleep(0.1)
