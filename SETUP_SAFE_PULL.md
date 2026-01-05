# Настройка скрипта safe_pull_server.sh на сервере

## Если скрипт не найден:

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# 1. Проверить, существует ли файл
ls -la safe_pull_server.sh

# 2. Если файла нет, получить обновления из GitHub
sudo git pull origin main

# 3. Установить права на выполнение
chmod +x safe_pull_server.sh

# 4. Проверить права
ls -la safe_pull_server.sh
# Должно быть: -rwxr-xr-x (или -rwxrwxr-x)

# 5. Запустить скрипт
sudo ./safe_pull_server.sh
```

## Если файл существует, но не запускается:

```bash
# Проверить права
ls -la safe_pull_server.sh

# Установить права на выполнение
chmod +x safe_pull_server.sh

# Проверить, что файл имеет правильный формат (должен начинаться с #!/bin/bash)
head -1 safe_pull_server.sh

# Запустить
sudo ./safe_pull_server.sh
```

## Альтернативный способ запуска:

Если права не устанавливаются, можно запустить напрямую через bash:

```bash
sudo bash safe_pull_server.sh
```

