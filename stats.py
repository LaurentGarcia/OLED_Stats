#!/usr/bin/env python3
"""
Enhanced OLED Stats Display for Raspberry Pi
Based on the original script by Michael Klements, enhanced with dynamic information
using psutil and a live clock.

Modify by Lauren Garcia to make more dynamic information
"""

import time
import subprocess
import psutil
import board
import busio
import gpiozero
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# Use gpiozero to control the reset pin
oled_reset_pin = gpiozero.OutputDevice(4, active_high=False)  # GPIO 4 for reset, active low

# Display Parameters
WIDTH = 128
HEIGHT = 64
BORDER = 5

# Display refresh interval (in seconds)
LOOPTIME = 1.0

# Use I2C for communication
i2c = board.I2C()

# Manually reset the display (high -> low -> high for reset pulse)
oled_reset_pin.on()
time.sleep(0.1)
oled_reset_pin.off()
time.sleep(0.1)
oled_reset_pin.on()

# Create the OLED display object (I2C address may be 0x3C or 0x3D)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C)

# Clear the display
oled.fill(0)
oled.show()

# Create a blank image for drawing
image = Image.new("1", (oled.width, oled.height))
draw = ImageDraw.Draw(image)

# (Optional) Draw a white background once if desired:
# draw.rectangle((0, 0, oled.width, oled.height), outline=255, fill=255)

# Load a custom font (make sure the .ttf file is in the same directory or specify its path)
# Adjust the font size as needed. Here we use two sizes: a larger one and a small one for extra info.
font_large = ImageFont.truetype('PixelOperator.ttf', 16)
font_small = ImageFont.truetype('PixelOperator.ttf', 12)

while True:
    # Clear the image by drawing a black rectangle over it.
    draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)

    # --- Dynamic Information Gathering ---

    # 1. IP Address (using the original shell command)
    try:
        ip = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True)
        ip_address = ip.decode('utf-8').strip()
    except Exception:
        ip_address = "N/A"

    # 2. CPU Usage (using psutil)
    cpu_percent = psutil.cpu_percent(interval=0.1)  # Quick measurement
    cpu_text = f"CPU: {cpu_percent:.1f}%"

    # 3. Memory Usage (using psutil)
    mem = psutil.virtual_memory()
    mem_used = mem.used / (1024 * 1024)   # in MB
    mem_total = mem.total / (1024 * 1024)   # in MB
    mem_text = f"Mem: {mem_used:.0f}/{mem_total:.0f}MB {mem.percent}%"

    # 4. Disk Usage (using psutil)
    disk = psutil.disk_usage('/')
    disk_used = disk.used / (1024 * 1024 * 1024)  # in GB
    disk_total = disk.total / (1024 * 1024 * 1024)  # in GB
    disk_text = f"Disk: {disk_used:.0f}/{disk_total:.0f}GB {disk.percent}%"

    # 5. Temperature (still using vcgencmd)
    try:
        temp = subprocess.check_output("vcgencmd measure_temp | cut -f2 -d'='", shell=True)
        temperature = temp.decode('utf-8').strip()
    except Exception:
        temperature = "N/A"

    # 6. Clock - current time (HH:MM:SS)
    current_time = time.strftime("%H:%M:%S")

    # --- Drawing on the OLED ---
    # You can adjust coordinates and fonts as needed.

    # Top line: IP address
    draw.text((0, 0), f"IP: {ip_address}", font=font_small, fill=255)

    # Second line: CPU usage (left) and Temperature (right)
    draw.text((0, 12), cpu_text, font=font_small, fill=255)
    draw.text((70, 12), f"Temp:{temperature}", font=font_small, fill=255)

    # Third line: Memory usage
    draw.text((0, 24), mem_text, font=font_small, fill=255)

    # Fourth line: Disk usage
    draw.text((0, 36), disk_text, font=font_small, fill=255)

    # Bottom line: Clock (could be centered or right aligned)
    draw.text((0, 48), f"Time: {current_time}", font=font_small, fill=255)

    # Update the OLED display with the image.
    oled.image(image)
    oled.show()

    # Wait before updating again.
    time.sleep(LOOPTIME)
