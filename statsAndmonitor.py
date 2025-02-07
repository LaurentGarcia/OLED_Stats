#!/usr/bin/env python3
"""
Enhanced OLED Stats Display for Raspberry Pi
Based on the original script by Michael Klements, enhanced with dynamic information
using psutil and a live clock.

Modify by Lauren Garcia to make more dynamic information

Enhanced OLED Stats Display with Horizontal Scrolling

Based on Michael Klements’ original script for the Raspberry Pi Desktop Case with OLED Stats Display.
This version keeps the IP line static on the first line while horizontally scrolling the CPU, memory,
and disk metrics if the text is wider than the 128×64 display.
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

# Create the OLED display object (typically at I2C address 0x3C)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)
oled.fill(0)
oled.show()

# Create an image buffer for drawing
image = Image.new('1', (WIDTH, HEIGHT))
draw = ImageDraw.Draw(image)

# Load fonts
try:
    main_font = ImageFont.truetype('PixelOperator.ttf', 16)
except Exception as e:
    print("Error loading PixelOperator.ttf, using default font:", e)
    main_font = ImageFont.load_default()

try:
    icon_font = ImageFont.truetype('lineawesome-webfont.ttf', 18)
except Exception as e:
    print("Error loading lineawesome-webfont.ttf, using default font:", e)
    icon_font = ImageFont.load_default()

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
        # Concatenate info for all disks (lines starting with /dev)
        metrics['Disk'] = subprocess.check_output("df -h | awk '$1 ~ /^\\/dev/ {printf \"%s:%s(%s) \", $1, $3, $5}'", shell=True).decode('utf-8').strip()
    except Exception:
        metrics['Disk'] = "N/A"
    return metrics

def draw_scrolling_text_infinite(y, text, offset):
    """
    Draw text with infinite horizontal scrolling at vertical position y.
    Returns updated offset.
    """
    # Use textbbox to get text dimensions (instead of deprecated textsize)
    bbox = draw.textbbox((0, 0), text, font=main_font)
    text_width = bbox[2] - bbox[0]
    if text_width <= WIDTH:
        draw.text((0, y), text, font=main_font, fill=255)
        return 0
    spacing = 20  # Gap between repetitions
    total_length = text_width + spacing
    effective_offset = offset % total_length
    draw.text((-effective_offset, y), text, font=main_font, fill=255)
    # Draw second instance if needed for seamless scrolling
    if text_width - effective_offset < WIDTH:
        draw.text((text_width - effective_offset + spacing, y), text, font=main_font, fill=255)
    return offset + 2  # Increase offset (adjust for scroll speed)

def display_scrolling_mode(metrics, offsets):
    """
    Display metrics in scrolling mode.
      - Line 0: Static IP.
      - Line 1: "CPU: <load> | Temp: <temp>" (scrolls).
      - Line 2: "Mem: <mem>" (scrolls).
      - Line 3: "Disk: <disk>" (scrolls).
    Returns updated offsets.
    """
    # Clear the image
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    # Draw static IP on line 0 (y=0)
    draw.text((0, 0), "IP: " + metrics['IP'], font=main_font, fill=255)
    # Prepare scrolling text lines
    cpu_text = "CPU: " + metrics['CPU'] + " | Temp: " + metrics['Temp']
    offsets['CPU'] = draw_scrolling_text_infinite(16, cpu_text, offsets['CPU'])
    offsets['Mem'] = draw_scrolling_text_infinite(32, "Mem: " + metrics['Mem'], offsets['Mem'])
    offsets['Disk'] = draw_scrolling_text_infinite(48, "Disk: " + metrics['Disk'], offsets['Disk'])
    oled.image(image)
    oled.show()
    return offsets

def display_icon_mode(metrics):
    """
    Display metrics in icon mode with a fixed layout and icons.
    Layout (with offsets):
      - Temperature icon (chr(62609)) and text at top-left.
      - Memory icon (chr(62776)) and text at top-right.
      - Disk icon (chr(63426)) and text below temperature.
      - CPU icon (chr(62171)) and text below memory.
      - WiFi/IP icon (chr(61931)) and IP text at the bottom.
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    padding = -2
    top = padding
    x = 0
    # Draw icons
    draw.text((x, top + 5), chr(62609), font=icon_font, fill=255)       # Temperature icon
    draw.text((x + 65, top + 5), chr(62776), font=icon_font, fill=255)    # Memory icon
    draw.text((x, top + 25), chr(63426), font=icon_font, fill=255)        # Disk icon
    draw.text((x + 65, top + 25), chr(62171), font=icon_font, fill=255)   # CPU icon
    draw.text((x, top + 45), chr(61931), font=icon_font, fill=255)        # WiFi/IP icon
    # Draw text next to icons
    draw.text((x + 19, top + 5), str(metrics['Temp']), font=main_font, fill=255)
    draw.text((x + 87, top + 5), str(metrics['Mem']), font=main_font, fill=255)
    draw.text((x + 19, top + 25), str(metrics['Disk']), font=main_font, fill=255)
    draw.text((x + 87, top + 25), str(metrics['CPU']), font=main_font, fill=255)
    draw.text((x + 19, top + 45), str(metrics['IP']), font=main_font, fill=255)
    oled.image(image)
    oled.show()

# ---------------------------
# Main Loop with Mode Switching
# ---------------------------
# Offsets for scrolling mode
offsets = {'CPU': 0, 'Mem': 0, 'Disk': 0}
current_mode = 0  # 0 = scrolling mode, 1 = icon mode
mode_start_time = time.time()

while True:
    # Toggle display mode every MODE_DURATION seconds
    if time.time() - mode_start_time >= MODE_DURATION:
        current_mode = 1 - current_mode  # Toggle between 0 and 1
        mode_start_time = time.time()

    # Update metrics (you can adjust the update frequency as desired)
    metrics = fetch_metrics()

    if current_mode == 0:
        # Scrolling mode: update more frequently for smooth animation
        offsets = display_scrolling_mode(metrics, offsets)
        time.sleep(0.1)
    else:
        # Icon mode: update every LOOPTIME seconds
        display_icon_mode(metrics)
        time.sleep(LOOPTIME)