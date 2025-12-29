# Быстрое обновление на сервере

## Если скрипт safe_pull_server.sh не найден:

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# 1. Разрешить конфликт (если есть)
sudo git checkout -- safe_pull_server.sh

# 2. Получить последние изменения
sudo git pull origin main

# 3. Дать права на выполнение скрипту
chmod +x safe_pull_server.sh

# 4. Запустить скрипт
sudo ./safe_pull_server.sh
```

## Или выполнить обновление вручную:

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# 1. Разрешить конфликт (если есть)
sudo git checkout -- safe_pull_server.sh

# 2. Получить последние изменения
sudo git pull origin main

# 3. Создать backup базы данных
if [ -f "./data/app.db" ]; then
    cp ./data/app.db ./data/app.db.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup создан"
fi

# 4. Пересобрать Docker образ
sudo docker compose build web

# 5. Перезапустить контейнер
sudo docker compose up -d web

# 6. Проверить статус
sudo docker compose ps
sudo docker compose logs --tail=20 web
```

