#!/usr/bin/env python3
"""
Enhanced OLED Stats Display for Raspberry Pi
Based on the original script by Michael Klements, enhanced with dynamic information
using psutil and a live clock.

Modify by Lauren Garcia to make more dynamic information
"""

import time
import psutil
import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# OLED display parameters
WIDTH = 128
HEIGHT = 64

# Initialize I2C and the OLED display (I2C address is typically 0x3C)
i2c = board.I2C()
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)

# Clear the display
oled.fill(0)
oled.show()

# Create an image buffer for drawing (1-bit color)
image = Image.new("1", (WIDTH, HEIGHT))
draw = ImageDraw.Draw(image)

# Try to load a custom font; if not available, load the default font.
# Adjust the font size to be small so more text lines fit.
try:
    font_small = ImageFont.truetype('PixelOperator.ttf', 10)
except IOError:
    font_small = ImageFont.load_default()

# Determine the line height and maximum number of lines that can fit on the screen.
line_height = font_small.getsize("A")[1]
max_lines = HEIGHT // line_height

# Duration (in seconds) to display each page of information.
page_duration = 5

def get_cpu_info():
    """Return a string with the current CPU load percentage."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    return f"CPU: {cpu_percent:.1f}%"

def get_disk_info():
    """
    Gather disk usage information for each partition.
    Returns a list of strings in the format:
      "<device>: <used>/<total>GB (<percent>%)"
    """
    disk_info = []
    partitions = psutil.disk_partitions(all=False)
    for part in partitions:
        try:
            usage = psutil.disk_usage(part.mountpoint)
            # Convert bytes to gigabytes
            used_gb = usage.used / (1024**3)
            total_gb = usage.total / (1024**3)
            # Extract the device name (e.g., sda1)
            dev_name = part.device.split('/')[-1]
            disk_line = f"{dev_name}: {used_gb:.1f}/{total_gb:.1f}GB {usage.percent}%"
            disk_info.append(disk_line)
        except Exception:
            continue
    return disk_info

def display_info():
    """Gathers system info and displays it on the OLED with pagination."""
    # Get CPU and disk info
    cpu_line = get_cpu_info()
    disk_lines = get_disk_info()

    # Combine all info; CPU info at the top
    all_lines = [cpu_line] + disk_lines

    # Calculate the total number of pages needed
    total_pages = (len(all_lines) + max_lines - 1) // max_lines

    for page in range(total_pages):
        # Clear the image buffer by drawing a black rectangle over the entire screen
        draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)

        # Determine the slice of lines to display on this page
        start_idx = page * max_lines
        end_idx = min(start_idx + max_lines, len(all_lines))
        page_lines = all_lines[start_idx:end_idx]

        # Draw each line on the image buffer
        for i, line in enumerate(page_lines):
            y = i * line_height
            draw.text((0, y), line, font=font_small, fill=255)

        # Update the OLED with the new image and pause to let the viewer read it
        oled.image(image)
        oled.show()
        time.sleep(page_duration)

def main():
    """Continuously update the OLED display with system information."""
    while True:
        display_info()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Clear the display before exiting
        oled.fill(0)
        oled.show()
        print("Exiting dynamic OLED display script.")