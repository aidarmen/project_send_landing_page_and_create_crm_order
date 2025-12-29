# Решение конфликта Git на сервере

Если при `git pull` возникает ошибка о локальных изменениях, выполните одну из следующих команд:

## Вариант 1: Принять версию с GitHub (рекомендуется, если локальные изменения не важны)

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# Отменить локальные изменения в файле
sudo git checkout -- safe_pull_server.sh

# Затем повторить pull
sudo git pull origin main
```

## Вариант 2: Сохранить локальные изменения и применить их позже

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# Сохранить локальные изменения
sudo git stash

# Получить изменения с GitHub
sudo git pull origin main

# Если нужно, вернуть локальные изменения
sudo git stash pop
```

## Вариант 3: Закоммитить локальные изменения (если они важны)

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# Добавить изменения
sudo git add safe_pull_server.sh

# Закоммитить
sudo git commit -m "Local changes to safe_pull_server.sh"

# Затем pull (может потребоваться разрешение конфликтов)
sudo git pull origin main
```

## После разрешения конфликта

После успешного `git pull`, выполните:

```bash
# Пересобрать Docker образ
sudo docker compose build web

# Перезапустить контейнер
sudo docker compose up -d web

# Проверить статус
sudo docker compose ps
```

