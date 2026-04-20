#!/usr/bin/env python3
"""
Создает .ico файл из PNG с несколькими размерами
"""

from PIL import Image
import os

def create_ico(input_path, output_path):
    """
    Создает .ico файл с несколькими размерами
    
    Args:
        input_path: путь к PNG файлу
        output_path: путь для сохранения .ico
    """
    print(f"Открываю {input_path}...")
    img = Image.open(input_path)
    
    # Размеры для .ico файла
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    
    print("Создаю иконки разных размеров...")
    icon_images = []
    for size in sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        icon_images.append(resized)
        print(f"  ✓ {size[0]}x{size[1]}")
    
    print(f"\nСохраняю {output_path}...")
    icon_images[0].save(
        output_path,
        format='ICO',
        sizes=sizes
    )
    print(f"✓ Готово!")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "icon.png")
    output_file = os.path.join(script_dir, "icon.ico")
    
    if not os.path.exists(input_file):
        print(f"❌ Ошибка: файл {input_file} не найден!")
        return
    
    print("=" * 50)
    print("Создание .ico файла")
    print("=" * 50)
    
    create_ico(input_file, output_file)
    
    print("\n" + "=" * 50)
    print("✓ Файл icon.ico создан!")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

