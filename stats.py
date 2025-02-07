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

# Display Parameters
WIDTH = 128
HEIGHT = 64
LOOPTIME = 1.0  # Update metrics every 1 second

# I2C Setup
i2c = board.I2C()

# Manually reset the display (high -> low -> high for reset pulse)
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

# Create a blank image for drawing
image = Image.new("1", (oled.width, oled.height))
draw = ImageDraw.Draw(image)

# Load the custom font (PixelOperator.ttf at size 16). If not found, use the default font.
try:
    font = ImageFont.truetype('PixelOperator.ttf', 16)
except Exception as e:
    print("Error loading custom font, using default:", e)
    font = ImageFont.load_default()

# ---------------------------
# Helper: Infinite Scrolling Text Function
# ---------------------------
def draw_scrolling_text_infinite(y, text, offset):
    """
    Draws text that scrolls infinitely horizontally on line starting at vertical position y.
    If the text is wider than the display, it scrolls with a gap before repeating.

    Parameters:
      y      - Vertical coordinate for drawing the text.
      text   - The text string to display.
      offset - The current horizontal scroll offset.

    Returns:
      The updated offset for the next iteration.
    """
    text_width, _ = draw.textsize(text, font=font)
    # If text fits in the display, just draw it and return 0 offset.
    if text_width <= WIDTH:
        draw.text((0, y), text, font=font, fill=255)
        return 0
    spacing = 20  # Gap (in pixels) between repetitions of the text.
    total_length = text_width + spacing
    # effective_offset is the offset modulo total_length for infinite scrolling.
    effective_offset = offset % total_length
    # Draw the first instance
    draw.text((-effective_offset, y), text, font=font, fill=255)
    # If needed, draw a second instance to create a seamless scroll.
    if text_width - effective_offset < WIDTH:
        draw.text((text_width - effective_offset + spacing, y), text, font=font, fill=255)
    return offset + 2  # Increase offset by 2 pixels per refresh (adjust for scroll speed)

# ---------------------------
# Offsets for each scrolling line
# ---------------------------
cpu_offset = 0
mem_offset = 0
disk_offset = 0

# ---------------------------
# Initialize Metric Variables
# ---------------------------
IP = "N/A"
cpu_text = "CPU: N/A"
mem_display = "Mem: N/A"
disk_text = "Disk: N/A"
temp_text = "Temp: N/A"

last_update = 0

# ---------------------------
# Main Loop
# ---------------------------
while True:
    current_time = time.time()
    # Update metrics every LOOPTIME seconds
    if current_time - last_update >= LOOPTIME:
        last_update = current_time
        try:
            IP = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True).decode('utf-8').strip()
        except Exception:
            IP = "N/A"
        try:
            CPU = subprocess.check_output("top -bn1 | grep load | awk '{printf \"CPU: %.2f\", $(NF-2)}'", shell=True).decode('utf-8').strip()
        except Exception:
            CPU = "CPU: N/A"
        try:
            Temp = subprocess.check_output("vcgencmd measure_temp | cut -f2 -d'='", shell=True).decode('utf-8').strip()
        except Exception:
            Temp = "Temp: N/A"
        try:
            MemUsage = subprocess.check_output("free -m | awk 'NR==2{printf \"Mem: %.1f/%.1fGB %s\", $3/1024,$2/1024,($3/$2)*100}'", shell=True).decode('utf-8').strip()
        except Exception:
            MemUsage = "Mem: N/A"
        try:
            # Use an awk command that prints info for all /dev disks in one line.
            Disk = subprocess.check_output("df -h | awk '$1 ~ /^\\/dev/ {printf \"%s:%s(%s) \", $1, $3, $5}'", shell=True).decode('utf-8').strip()
        except Exception:
            Disk = "Disk: N/A"

        # Combine CPU and Temperature into one string for line 1.
        cpu_text = CPU + " | " + Temp
        mem_display = MemUsage
        disk_text = Disk

    # Clear the image (fill with black)
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)

    # Draw the static IP line on line 0 (y=0)
    draw.text((0, 0), "IP: " + IP, font=font, fill=255)

    # Draw infinite scrolling for dynamic metrics:
    cpu_offset = draw_scrolling_text_infinite(16, cpu_text, cpu_offset)
    mem_offset = draw_scrolling_text_infinite(32, mem_display, mem_offset)
    disk_offset = draw_scrolling_text_infinite(48, disk_text, disk_offset)

    # Update the OLED display with the current image
    oled.image(image)
    oled.show()

    # Short sleep for smooth scrolling (adjust as needed)
    time.sleep(0.1)