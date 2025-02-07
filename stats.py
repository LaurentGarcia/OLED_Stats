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

# Use gpiozero to control the reset pin (GPIO 4, active low)
oled_reset_pin = gpiozero.OutputDevice(4, active_high=False)

# Display parameters
WIDTH = 128
HEIGHT = 64
LOOPTIME = 1.0  # How often (in seconds) to update metrics

# I2C setup
i2c = board.I2C()

# Manually reset the display: high -> low -> high (for reset pulse)
oled_reset_pin.on()
time.sleep(0.1)
oled_reset_pin.off()
time.sleep(0.1)
oled_reset_pin.on()

# Create the OLED display object (I2C address usually 0x3C)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)

# Clear the display
oled.fill(0)
oled.show()

# Create a blank image for drawing and get a drawing object
image = Image.new("1", (oled.width, oled.height))
draw = ImageDraw.Draw(image)

# Load font (using PixelOperator.ttf at size 16; adjust path/size if needed)
try:
    font = ImageFont.truetype('PixelOperator.ttf', 16)
except Exception as e:
    print("Error loading custom font, using default:", e)
    font = ImageFont.load_default()

# ---------------------------
# Helper Function: Scrolling Text
# ---------------------------
def draw_scrolling_text(y, text, offset):
    """
    Draws the given text on line starting at vertical position y,
    scrolling horizontally if its width exceeds the display width.

    Parameters:
      y      - vertical coordinate where the text is drawn.
      text   - the text string to display.
      offset - the current horizontal offset (in pixels) for scrolling.

    Returns:
      The updated offset for the next iteration.
    """
    text_width, _ = draw.textsize(text, font=font)
    if text_width <= WIDTH:
        # If the text fits within the display width, draw it normally at x=0.
        draw.text((0, y), text, font=font, fill=255)
        return 0  # No scrolling needed; reset offset.
    else:
        # If text is too wide, scroll it horizontally.
        if offset > text_width - WIDTH:
            offset = 0  # Reset scrolling when the end is reached.
        # Draw text shifted to the left by 'offset' pixels.
        draw.text((-offset, y), text, font=font, fill=255)
        return offset + 2  # Increase offset for next update (adjust '2' for scroll speed)

# ---------------------------
# Offsets for scrolling on each dynamic line
# ---------------------------
cpu_offset = 0
mem_offset = 0
disk_offset = 0

# ---------------------------
# Main Loop
# ---------------------------
while True:
    # ---------------------------
    # Gather Metrics
    # ---------------------------
    try:
        # Get IP address
        cmd = "hostname -I | cut -d' ' -f1"
        IP = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except Exception:
        IP = "N/A"

    try:
        # Get CPU load (using top command)
        cmd = "top -bn1 | grep load | awk '{printf \"CPU: %.2f\", $(NF-2)}'"
        CPU = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except Exception:
        CPU = "CPU: N/A"

    try:
        # Get temperature
        cmd = "vcgencmd measure_temp | cut -f2 -d'='"
        Temp = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except Exception:
        Temp = "Temp: N/A"

    try:
        # Get memory usage
        cmd = "free -m | awk 'NR==2{printf \"Mem: %.1f/%.1fGB %s\", $3/1024,$2/1024,($3/$2)*100}'"
        MemUsage = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except Exception:
        MemUsage = "Mem: N/A"

    try:
        # Get disk usage; modify command as needed to include multiple disks.
        cmd = "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'"
        Disk = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except Exception:
        Disk = "Disk: N/A"

    # Combine CPU and temperature into one string.
    cpu_text = CPU + " | " + Temp
    # Use MemUsage and Disk directly.
    mem_text = MemUsage
    disk_text = Disk

    # ---------------------------
    # Scroll Animation within this update cycle
    # ---------------------------
    # To get smooth scrolling, update the display several times within LOOPTIME.
    refresh_interval = 0.1  # seconds per scroll update
    iterations = int(LOOPTIME / refresh_interval)

    for i in range(iterations):
        # Clear the image (fill with black)
        draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)

        # Draw static IP line (Line 0 at y=0)
        draw.text((0, 0), "IP: " + IP, font=font, fill=255)

        # Draw scrolling CPU and Temp on Line 1 (y = 16)
        cpu_offset = draw_scrolling_text(16, cpu_text, cpu_offset)

        # Draw scrolling Memory usage on Line 2 (y = 32)
        mem_offset = draw_scrolling_text(32, mem_text, mem_offset)

        # Draw scrolling Disk info on Line 3 (y = 48)
        disk_offset = draw_scrolling_text(48, disk_text, disk_offset)

        # Update the OLED display with the current image buffer
        oled.image(image)
        oled.show()

        time.sleep(refresh_interval)
