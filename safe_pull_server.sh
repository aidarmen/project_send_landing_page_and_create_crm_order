#!/bin/bash

# Скрипт для безопасного обновления на сервере без потери базы данных
# Использование: ./safe_pull_server.sh

set -e  # Остановить при ошибке

echo "=== Безопасное обновление на сервере ==="
echo ""

# Определить директорию проекта
# Если скрипт запущен из директории проекта, используем текущую директорию
# Иначе пробуем стандартные пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR=""

# Проверяем, запущен ли скрипт из директории проекта
if [ -f "$SCRIPT_DIR/docker-compose.yml" ] && [ -f "$SCRIPT_DIR/app.py" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
elif [ -f "./docker-compose.yml" ] && [ -f "./app.py" ]; then
    PROJECT_DIR="$(pwd)"
elif [ -d "$HOME/projects/project_send_landing_page_and_create_crm_order" ]; then
    PROJECT_DIR="$HOME/projects/project_send_landing_page_and_create_crm_order"
elif [ -d "/home/admin_c2o/projects/project_send_landing_page_and_create_crm_order" ]; then
    PROJECT_DIR="/home/admin_c2o/projects/project_send_landing_page_and_create_crm_order"
else
    echo "❌ Ошибка: Директория проекта не найдена."
    echo "   Пожалуйста, запустите скрипт из директории проекта или укажите путь."
    exit 1
fi

# Перейти в директорию проекта
cd "$PROJECT_DIR" || { 
    echo "❌ Ошибка: Не удалось перейти в директорию проекта: $PROJECT_DIR"
    exit 1
}

echo "📂 Текущая директория: $(pwd)"
echo ""

# 1. Создать backup базы данных (на всякий случай)
echo "💾 Создание backup базы данных..."
BACKUP_CREATED=false
BACKUP_FILE=""

# Проверить и создать backup из ./data/app.db (основная база)
if [ -f "./data/app.db" ]; then
    BACKUP_FILE="./data/app.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp ./data/app.db "$BACKUP_FILE"
    echo "✅ Backup создан из ./data/app.db: $BACKUP_FILE"
    BACKUP_CREATED=true
    
    # Проверить содержимое backup
    USERS_COUNT=$(sudo docker compose exec -T web python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('/app/data/app.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    print(count)
    conn.close()
except:
    print('0')
" 2>/dev/null || echo "0")
    
    if [ "$USERS_COUNT" -gt 0 ]; then
        echo "   ✓ Backup содержит $USERS_COUNT пользователей"
    else
        echo "   ⚠️  Backup пустой или не содержит пользователей"
    fi
fi

# Проверить, есть ли база данных в /app/app.db внутри контейнера
echo ""
echo "🔍 Проверка дополнительных баз данных в контейнере..."
ROOT_DB_EXISTS=$(sudo docker compose exec -T web test -f /app/app.db && echo "yes" || echo "no" 2>/dev/null)

if [ "$ROOT_DB_EXISTS" = "yes" ]; then
    echo "   Найдена база данных в /app/app.db"
    
    # Проверить содержимое
    ROOT_USERS=$(sudo docker compose exec -T web python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('/app/app.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    print(count)
    conn.close()
except:
    print('0')
" 2>/dev/null || echo "0")
    
    if [ "$ROOT_USERS" -gt 0 ]; then
        echo "   ✓ /app/app.db содержит $ROOT_USERS пользователей"
        
        # Создать backup из /app/app.db
        ROOT_BACKUP_NAME="app.db.backup.from_root.$(date +%Y%m%d_%H%M%S)"
        ROOT_BACKUP="./data/$ROOT_BACKUP_NAME"
        sudo docker compose exec -T web cp /app/app.db "/app/data/$ROOT_BACKUP_NAME"
        echo "   ✅ Backup создан из /app/app.db: $ROOT_BACKUP"
        
        # Если основная база пустая или содержит меньше данных, скопировать из /app/app.db
        if [ "$USERS_COUNT" -eq 0 ] || [ "$ROOT_USERS" -gt "$USERS_COUNT" ]; then
            echo ""
            echo "⚠️  Обнаружено: /app/app.db содержит больше данных!"
            echo "   Копирую данные из /app/app.db в /app/data/app.db..."
            sudo docker compose exec -T web cp /app/app.db /app/data/app.db
            sudo chown admin_c2o:admin_c2o ./data/app.db 2>/dev/null || true
            sudo chmod 644 ./data/app.db 2>/dev/null || true
            echo "   ✅ Данные скопированы"
        fi
    else
        echo "   ⚠️  /app/app.db пустая"
    fi
fi

if [ "$BACKUP_CREATED" = false ] && [ "$ROOT_DB_EXISTS" = "no" ]; then
    echo "⚠️  База данных не найдена ни в ./data/app.db, ни в /app/app.db"
fi
echo ""

# 2. Проверить статус Git и разрешить конфликты перед pull
echo "📋 Проверка статуса Git..."
git status
echo ""

# 2.1. Отменить локальные изменения в критических файлах ПЕРЕД pull
echo "🔧 Проверка и разрешение локальных изменений..."
MODIFIED_FILES=$(git diff --name-only HEAD 2>/dev/null || echo "")

if [ -n "$MODIFIED_FILES" ]; then
    echo "   Найдены локальные изменения в: $MODIFIED_FILES"
    
    # Для safe_pull_server.sh - всегда принимать версию с GitHub
    if echo "$MODIFIED_FILES" | grep -q "safe_pull_server.sh"; then
        echo "   ⚠️  Обнаружены локальные изменения в safe_pull_server.sh"
        echo "   Отменяю локальные изменения (принимаю версию с GitHub)..."
        # Попробовать отменить без sudo, затем с sudo
        if ! git checkout -- safe_pull_server.sh 2>/dev/null; then
            sudo git checkout -- safe_pull_server.sh 2>/dev/null || {
                echo "   ⚠️  Не удалось отменить изменения автоматически"
                echo "   Попытка будет сделана после получения изменений"
            }
        fi
        echo "   ✅ Локальные изменения отменены"
    fi
fi

# 2.2. Проверить, есть ли незакоммиченные изменения, которые могут помешать pull
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || echo "")
if [ -n "$STAGED_FILES" ]; then
    echo "   Найдены staged изменения. Они не будут затронуты."
fi

# 3. Получить последние изменения
echo "⬇️  Получение изменений из GitHub..."

# Сначала попробовать обычный pull
if ! git pull origin main 2>&1; then
    echo ""
    echo "⚠️  Git pull завершился с ошибкой"
    echo "   Попытка разрешить автоматически..."
    
    # Проверить, есть ли еще локальные изменения
    REMAINING_MODIFIED=$(git diff --name-only HEAD 2>/dev/null | grep -v "^$" || echo "")
    if [ -n "$REMAINING_MODIFIED" ]; then
        echo "   Отменяю оставшиеся локальные изменения..."
        for file in $REMAINING_MODIFIED; do
            echo "     Отмена изменений в: $file"
            if ! git checkout -- "$file" 2>/dev/null; then
                sudo git checkout -- "$file" 2>/dev/null || true
            fi
        done
        # Также попробовать отменить все изменения сразу
        git checkout -- . 2>/dev/null || sudo git checkout -- . 2>/dev/null || true
    fi
    
    # Попробовать pull снова
    echo "   Повторная попытка pull..."
    if ! git pull origin main 2>&1; then
        echo ""
        echo "   ❌ Не удалось автоматически разрешить конфликты"
        echo "   Пожалуйста, выполните вручную:"
        echo "      sudo git checkout -- safe_pull_server.sh"
        echo "      sudo git pull origin main"
        exit 1
    fi
fi
echo ""

# 4. Пересобрать Docker образ (без удаления контейнеров)
echo "🔨 Пересборка Docker образа..."
sudo docker compose build web
echo ""

# 5. Перезапустить контейнер (это НЕ удалит volumes)
echo "🔄 Перезапуск контейнера..."
sudo docker compose up -d web

# Подождать, пока контейнер запустится
echo "   Ожидание запуска контейнера..."
sleep 5
echo ""

# 6. Проверить статус контейнера
echo "📊 Статус контейнеров:"
sudo docker compose ps
echo ""

# 7. Показать логи (последние 20 строк)
echo "📝 Последние логи:"
sudo docker compose logs --tail=20 web
echo ""

echo "✅ Обновление завершено!"
echo ""
echo "⚠️  Важно:"
echo "   - База данных сохранена в ./data/app.db"
if [ -n "$BACKUP_FILE" ]; then
    echo "   - Backup создан: $BACKUP_FILE"
fi
echo "   - Если что-то пошло не так, можно восстановить из backup"
echo ""
echo "📝 Проверка финального состояния базы данных:"
FINAL_CHECK=$(sudo docker compose exec -T web python3 -c "
import sys
sys.path.insert(0, '/app')
import sqlite3
import os

# Проверить, какой путь использует приложение
try:
    from db import DB_PATH
    print(f'✅ Приложение использует: {DB_PATH}')
except Exception as e:
    print(f'⚠️ Ошибка импорта db: {e}')
    DB_PATH = '/app/data/app.db'
    print(f'   Используется путь по умолчанию: {DB_PATH}')

# Проверить, существует ли база
if os.path.exists(DB_PATH):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM links')
        links = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM offers')
        offers = c.fetchone()[0]
        print(f'✅ Данные: Users={users}, Links={links}, Offers={offers}')
        conn.close()
    except Exception as e:
        print(f'❌ Ошибка чтения базы: {e}')
else:
    print(f'❌ База данных не найдена по пути: {DB_PATH}')
    
    # Проверить альтернативные пути
    alt_paths = ['/app/data/app.db', '/app/app.db']
    found_alt = False
    for alt_path in alt_paths:
        if os.path.exists(alt_path):
            print(f'⚠️ Найдена база в альтернативном месте: {alt_path}')
            try:
                conn = sqlite3.connect(alt_path)
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM users')
                users = c.fetchone()[0]
                c.execute('SELECT COUNT(*) FROM links')
                links = c.fetchone()[0]
                print(f'   Users: {users}, Links: {links}')
                conn.close()
                found_alt = True
            except Exception as e:
                print(f'   Ошибка чтения: {e}')
    
    if not found_alt:
        print('❌ База данных не найдена ни в одном из мест')
" 2>/dev/null || echo "Ошибка при проверке")
echo "$FINAL_CHECK"
echo ""

