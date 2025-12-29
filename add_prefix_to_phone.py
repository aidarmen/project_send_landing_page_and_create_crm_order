#!/usr/bin/env python3
"""
Добавление префикса "7" к значениям в колонке phone для получения 11-значных номеров
"""

import pandas as pd
import os

file_path = 'batches/batch_100_v2.xlsx'
prefix = '7'
column_name = 'phone'
target_length = 11  # Стандартная длина казахстанского номера: 7XXXXXXXXXX

print(f"📖 Чтение файла: {file_path}")

try:
    # Читаем Excel файл
    df = pd.read_excel(file_path)

    if column_name not in df.columns:
        print(f"❌ Ошибка: Колонка '{column_name}' не найдена в файле.")
        print(f"   Доступные колонки: {', '.join(df.columns.tolist())}")
        exit(1)

    print(f"✅ Файл прочитан. Строк: {len(df)}")
    print(f"\n📝 Примеры значений ДО обновления:")
    for i in range(min(10, len(df))):
        val = df.at[df.index[i], column_name]
        print(f"   Строка {i+1}: {val}")

    # Обрабатываем каждое значение
    updated_count = 0
    phones_updated = []
    
    for idx in df.index:
        phone_val = df.at[idx, column_name]
        original_val = phone_val
        
        # Пропускаем пустые значения
        if pd.isna(phone_val):
            continue
        
        # Конвертируем в строку и убираем пробелы
        phone_str = str(phone_val).strip()
        
        # Пропускаем специальные значения
        if phone_str in ['nan', 'None', '', 'NaT']:
            continue
        
        # Убираем все нецифровые символы (точки, пробелы и т.д.)
        digits_only = ''.join(filter(str.isdigit, phone_str))
        
        if not digits_only:
            continue
        
        # Нормализуем номер до 11 цифр
        new_phone = digits_only
        
        # Если номер не начинается с "7", добавляем "7"
        if not digits_only.startswith('7'):
            new_phone = prefix + digits_only
        
        # Если номер начинается с "7" но имеет меньше 11 цифр, добавляем еще одну "7" в начало
        # Это для случаев, когда номер хранится как 10-значный (например, "7089244226")
        if new_phone.startswith('7') and len(new_phone) < target_length:
            # Добавляем еще одну "7" в начало: "7089244226" -> "77089244226"
            new_phone = prefix + new_phone
        
        # Если номер слишком длинный, обрезаем до 11 цифр
        if len(new_phone) > target_length:
            new_phone = new_phone[:target_length]
        
        # Обновляем значение, если оно изменилось или имеет неправильную длину
        if new_phone != digits_only or len(new_phone) != target_length:
            # Сохраняем как строку, чтобы сохранить формат и ведущий "7"
            df.at[idx, column_name] = new_phone
            updated_count += 1
            phones_updated.append((idx+1, original_val, new_phone))
        else:
            # Убеждаемся, что значение сохранено как строка
            df.at[idx, column_name] = str(new_phone)
    
    print(f"\n📊 Статистика:")
    print(f"   Обновлено значений: {updated_count}")
    if phones_updated:
        print(f"\n   Примеры обновленных телефонов:")
        for row_num, old_val, new_val in phones_updated[:10]:
            print(f"   Строка {row_num}: {old_val} -> {new_val} (длина: {len(new_val)})")

    print(f"\n📝 Примеры значений ПОСЛЕ обновления:")
    for i in range(min(10, len(df))):
        val = df.at[df.index[i], column_name]
        print(f"   Строка {i+1}: {val} (длина: {len(str(val))})")

    print(f"\n💾 Сохранение файла: {file_path}")
    # Сохраняем обновленный DataFrame обратно в Excel файл
    # Убеждаемся, что колонка phone сохранена как текст
    df[column_name] = df[column_name].astype(str)
    df.to_excel(file_path, index=False)
    print("✅ Файл успешно обновлен!")

except FileNotFoundError:
    print(f"❌ Ошибка: Файл не найден: {file_path}")
except PermissionError:
    print("❌ Ошибка: Файл открыт в другой программе (Excel, etc.)")
    print("   Закройте файл и попробуйте снова.")
except Exception as e:
    print(f"❌ Неожиданная ошибка: {e}")
    import traceback
    traceback.print_exc()
