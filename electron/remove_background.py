#!/usr/bin/env python3
"""
Скрипт для удаления белого фона с иконки и создания версий для трея
"""

from PIL import Image
import os

def remove_white_background(input_path, output_path, threshold=240):
    """
    Удаляет белый фон с изображения
    
    Args:
        input_path: путь к исходному изображению
        output_path: путь для сохранения результата
        threshold: порог для определения "белого" цвета (0-255)
    """
    print(f"Открываю {input_path}...")
    img = Image.open(input_path)
    img = img.convert("RGBA")
    
    datas = img.getdata()
    new_data = []
    
    print("Удаляю белый фон...")
    for item in datas:
        # Если пиксель близок к белому - делаем прозрачным
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0))  # Прозрачный
        else:
            new_data.append(item)
    
    img.putdata(new_data)
    img.save(output_path, "PNG")
    print(f"✓ Сохранено: {output_path}")
    return img

def create_tray_icon(img, output_path, size=32):
    """
    Создает маленькую иконку для трея
    
    Args:
        img: PIL Image объект
        output_path: путь для сохранения
        size: размер иконки (по умолчанию 32x32)
    """
    print(f"Создаю иконку для трея {size}x{size}...")
    tray_img = img.resize((size, size), Image.Resampling.LANCZOS)
    tray_img.save(output_path, "PNG")
    print(f"✓ Сохранено: {output_path}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "icon.png")
    output_file = os.path.join(script_dir, "icon_transparent.png")
    tray_file = os.path.join(script_dir, "tray-icon.png")
    
    if not os.path.exists(input_file):
        print(f"❌ Ошибка: файл {input_file} не найден!")
        return
    
    print("=" * 50)
    print("Удаление белого фона с иконки")
    print("=" * 50)
    
    # Удаляем белый фон
    img_transparent = remove_white_background(input_file, output_file)
    
    # Создаем иконку для трея
    create_tray_icon(img_transparent, tray_file, size=32)
    
    print("\n" + "=" * 50)
    print("✓ Готово!")
    print("=" * 50)
    print(f"\nСозданы файлы:")
    print(f"  1. {output_file} - иконка с прозрачным фоном")
    print(f"  2. {tray_file} - маленькая иконка для трея")
    print(f"\nТеперь:")
    print(f"  1. Замените icon.png на icon_transparent.png")
    print(f"  2. Пересоберите приложение: npm run build:win")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nВозможно нужно установить Pillow:")
        print("  pip install Pillow")
