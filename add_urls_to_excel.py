#!/usr/bin/env python3
"""
Добавление URL из CSV в Excel файл по customer_account_id
Создает колонку 'text' с шаблоном текста и URL
"""

import pandas as pd
import os

# Пути к файлам
csv_file = 'batches/upload_2_links.csv'
excel_file = 'batches/batch_100_v2.xlsx'
output_file = 'batches/batch_100_v2.xlsx'

# Шаблон текста
TEXT_TEMPLATE = """1 250 ₸ • ваша SIM-карта от Казахтелеком 🎁📱
🛜 40 ГБ | 📲 250 мин | 💬 100 SMS | 📺 TV+ Free
Перейдите со своим номером 🔄📱
Успейте до Нового года! 🎄✨
👉 {url}"""

print(f"📖 Чтение CSV файла: {csv_file}")
try:
    # Читаем CSV файл, пробуем разные варианты
    # Сначала пробуем с точкой с запятой
    try:
        df_csv = pd.read_csv(csv_file, delimiter=';', encoding='utf-8-sig')
        # Проверяем, не является ли первая строка sep=,
        if len(df_csv.columns) == 1 or 'sep=' in str(df_csv.columns[0]).lower():
            # Перечитываем, пропуская первую строку
            df_csv = pd.read_csv(csv_file, delimiter=';', encoding='utf-8-sig', skiprows=1)
    except:
        # Пробуем с запятой
        try:
            df_csv = pd.read_csv(csv_file, delimiter=',', encoding='utf-8-sig')
            if len(df_csv.columns) == 1 or 'sep=' in str(df_csv.columns[0]).lower():
                df_csv = pd.read_csv(csv_file, delimiter=',', encoding='utf-8-sig', skiprows=1)
        except:
            # Пробуем автоматическое определение
            df_csv = pd.read_csv(csv_file, encoding='utf-8-sig')
            if len(df_csv.columns) == 1 or 'sep=' in str(df_csv.columns[0]).lower():
                df_csv = pd.read_csv(csv_file, encoding='utf-8-sig', skiprows=1)
    
    print(f"✅ CSV прочитан. Строк: {len(df_csv)}")
    print(f"📋 Колонки CSV: {', '.join(df_csv.columns.tolist())}")
    
    # Показываем первые несколько строк для отладки
    if len(df_csv) > 0:
        print(f"\n📝 Первая строка CSV:")
        print(df_csv.iloc[0].to_dict())
except Exception as e:
    print(f"❌ Ошибка при чтении CSV: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print(f"\n📖 Чтение Excel файла: {excel_file}")
try:
    df_excel = pd.read_excel(excel_file)
    print(f"✅ Excel прочитан. Строк: {len(df_excel)}")
    print(f"📋 Колонки Excel: {', '.join(df_excel.columns.tolist())}")
except Exception as e:
    print(f"❌ Ошибка при чтении Excel: {e}")
    exit(1)

# Проверяем наличие необходимых колонок
if 'customer_account_id' not in df_excel.columns:
    print(f"❌ Ошибка: В Excel файле отсутствует колонка 'customer_account_id'")
    print(f"   Доступные колонки: {', '.join(df_excel.columns.tolist())}")
    exit(1)

if 'customer_account_id' not in df_csv.columns:
    print(f"❌ Ошибка: В CSV файле отсутствует колонка 'customer_account_id'")
    exit(1)

if 'url' not in df_csv.columns:
    print(f"❌ Ошибка: В CSV файле отсутствует колонка 'url'")
    exit(1)

print(f"\n🔗 Сопоставление данных по customer_account_id...")

# Создаем словарь для быстрого поиска URL по customer_account_id
url_dict = {}
for idx, row in df_csv.iterrows():
    customer_id = row.get('customer_account_id')
    url = row.get('url', '')
    if pd.notna(customer_id) and pd.notna(url) and url:
        # Преобразуем customer_id в int для сопоставления
        try:
            customer_id_int = int(float(str(customer_id)))
            url_dict[customer_id_int] = str(url).strip()
        except (ValueError, TypeError):
            continue

print(f"✅ Найдено {len(url_dict)} URL в CSV")

# Добавляем колонку text в Excel
matched = 0
not_matched = []

df_excel['text'] = ''

for idx, row in df_excel.iterrows():
    customer_id = row.get('customer_account_id')
    if pd.notna(customer_id):
        try:
            customer_id_int = int(float(str(customer_id)))
            if customer_id_int in url_dict:
                url = url_dict[customer_id_int]
                text = TEXT_TEMPLATE.format(url=url)
                df_excel.at[idx, 'text'] = text
                matched += 1
            else:
                not_matched.append(customer_id_int)
        except (ValueError, TypeError):
            not_matched.append(str(customer_id))

print(f"\n📊 Результаты:")
print(f"   ✅ Сопоставлено: {matched} строк")
print(f"   ⚠️  Не найдено URL: {len(not_matched)} строк")

if not_matched and len(not_matched) <= 10:
    print(f"   Не найденные customer_account_id: {not_matched[:10]}")
elif not_matched:
    print(f"   Не найденные customer_account_id (первые 10): {not_matched[:10]}")

# Сохраняем обновленный Excel файл
print(f"\n💾 Сохранение в файл: {output_file}")
try:
    df_excel.to_excel(output_file, index=False)
    print(f"✅ Файл успешно сохранен!")
    print(f"   Добавлена колонка 'text' с {matched} заполненными значениями")
except PermissionError:
    print(f"❌ Ошибка: Файл открыт в другой программе (Excel, etc.)")
    print(f"   Закройте файл и попробуйте снова.")
except Exception as e:
    print(f"❌ Ошибка при сохранении: {e}")

print(f"\n✅ Готово!")

