"""
Simple script to create placeholder icons for demo apps
Requires: pip install pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(text, bg_color, text_color, filename):
    """Create a simple icon with text"""
    size = 512
    img = Image.new('RGB', (size, size), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 200)
    except:
        font = ImageFont.load_default()
    
    # Get text size and center it
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) / 2
    y = (size - text_height) / 2
    
    # Draw text
    draw.text((x, y), text, fill=text_color, font=font)
    
    # Save
    img.save(filename)
    print(f"Created: {filename}")

# Create icons for each app
icons = [
    ("📊", "#667eea", "#ffffff", "crm-app/icon.png"),      # CRM - purple
    ("📧", "#3b82f6", "#ffffff", "mail-app/icon.png"),     # Mail - blue
    ("💰", "#003d7a", "#ffffff", "1c-app/icon.png"),       # 1C - dark blue
    ("📦", "#f97316", "#ffffff", "warehouse-app/icon.png"), # Warehouse - orange
]

print("Creating placeholder icons...")
print("Note: For better icons, use https://icons8.com or https://www.flaticon.com")
print()

for emoji, bg, fg, path in icons:
    try:
        create_icon(emoji, bg, fg, path)
    except Exception as e:
        print(f"Error creating {path}: {e}")

print()
print("Done! Icons created.")
print("For production, replace these with professional icons.")
