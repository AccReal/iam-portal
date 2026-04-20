"""
Create simple colored icons for demo apps
Requires: pip install pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_simple_icon(bg_color, icon_text, filename):
    """Create a simple colored icon with text"""
    size = 512
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded rectangle
    margin = 50
    draw.rounded_rectangle(
        [(margin, margin), (size - margin, size - margin)],
        radius=80,
        fill=bg_color
    )
    
    # Try to use a nice font
    try:
        font = ImageFont.truetype("arial.ttf", 180)
    except:
        try:
            font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 180)
        except:
            font = ImageFont.load_default()
    
    # Draw text in center
    bbox = draw.textbbox((0, 0), icon_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) / 2
    y = (size - text_height) / 2 - 20
    
    draw.text((x, y), icon_text, fill='white', font=font)
    
    # Save
    img.save(filename, 'PNG')
    print(f"✓ Created: {filename}")

print("Creating simple icons for demo applications...")
print()

# Create icons
icons = [
    ("#667eea", "📊", "crm-app/icon.png"),           # CRM - purple
    ("#3b82f6", "📧", "mail-app/icon.png"),          # Mail - blue
    ("#003d7a", "💰", "1c-app/icon.png"),            # 1C - dark blue
    ("#f97316", "📦", "warehouse-app/icon.png"),     # Warehouse - orange
]

for bg_color, emoji, path in icons:
    try:
        create_simple_icon(bg_color, emoji, path)
    except Exception as e:
        print(f"✗ Error creating {path}: {e}")

print()
print("Done! Icons created.")
print()
print("Note: These are simple placeholder icons.")
print("For better quality, download professional icons from:")
print("  - https://icons8.com")
print("  - https://www.flaticon.com")
print("  - https://iconscout.com")
