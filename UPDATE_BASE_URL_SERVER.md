# Обновление BASE_URL на сервере

## Вариант 1: Использовать sudo tee (рекомендуется)

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# Проверить, существует ли .env файл
ls -la .env

# Если файл существует, проверить его содержимое
cat .env | grep BASE_URL

# Добавить BASE_URL (если его нет) или обновить существующий
# Если BASE_URL уже есть, сначала удалите старую строку:
sudo sed -i '/^BASE_URL=/d' .env

# Затем добавьте новую строку
echo "BASE_URL=https://b2c2.telecom.kz" | sudo tee -a .env

# Проверить, что добавлено правильно
cat .env | grep BASE_URL
```

## Вариант 2: Использовать sudo bash -c

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# Удалить старую строку BASE_URL (если есть)
sudo bash -c 'sed -i "/^BASE_URL=/d" .env'

# Добавить новую строку
sudo bash -c 'echo "BASE_URL=https://b2c2.telecom.kz" >> .env'

# Проверить
cat .env | grep BASE_URL
```

## Вариант 3: Редактировать файл напрямую

```bash
cd ~/projects/project_send_landing_page_and_create_crm_order

# Открыть файл для редактирования
sudo nano .env

# Или использовать vim
sudo vim .env
```

В редакторе:
- Найдите строку `BASE_URL=...` (если есть)
- Измените на `BASE_URL=https://b2c2.telecom.kz`
- Или добавьте новую строку, если её нет
- Сохраните файл (в nano: Ctrl+O, Enter, Ctrl+X; в vim: Esc, :wq, Enter)

## После обновления .env:

```bash
# Перезапустить контейнер, чтобы применить изменения
sudo docker compose restart web

# Проверить логи, чтобы убедиться, что BASE_URL загружен правильно
sudo docker compose logs web | grep BASE_URL
```

## Проверка, что BASE_URL установлен правильно:

```bash
# Проверить переменные окружения внутри контейнера
sudo docker compose exec web env | grep BASE_URL

# Проверить логи приложения при запуске
sudo docker compose logs web | head -20
```

