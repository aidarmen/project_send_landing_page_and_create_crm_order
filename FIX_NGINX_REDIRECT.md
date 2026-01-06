# Исправление редиректа в Nginx

Проблема: на сервере настроен редирект с `https://b2c2.telecom.kz/` на `https://b2c2.telecom.kz/admin/`, который мешает редиректу на `telecom.kz`.

## Шаг 1: Найти конфигурацию Nginx

```bash
# Обычно конфигурация Nginx находится в одном из этих мест:
# - /etc/nginx/sites-available/b2c2.telecom.kz
# - /etc/nginx/sites-available/default
# - /etc/nginx/conf.d/b2c2.telecom.kz.conf
# - /etc/nginx/nginx.conf

# Найти файл конфигурации для b2c2.telecom.kz
sudo grep -r "b2c2.telecom.kz" /etc/nginx/

# Или найти все файлы конфигурации
ls -la /etc/nginx/sites-available/
ls -la /etc/nginx/conf.d/
```

## Шаг 2: Проверить текущую конфигурацию

```bash
# Открыть файл конфигурации (замените путь на найденный)
sudo nano /etc/nginx/sites-available/b2c2.telecom.kz
# Или
sudo nano /etc/nginx/conf.d/b2c2.telecom.kz.conf
```

## Шаг 3: Найти и удалить редирект на /admin/

В файле конфигурации найдите что-то вроде:

```nginx
location / {
    return 301 /admin/;
}
```

Или:

```nginx
location = / {
    return 301 /admin/;
}
```

**Удалите эти строки!**

## Шаг 4: Правильная конфигурация должна быть такой:

```nginx
server {
    listen 443 ssl http2;
    server_name b2c2.telecom.kz;

    # SSL сертификаты (ваши пути)
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Проксирование на Flask приложение
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # НЕ добавляйте редирект здесь!
        # Flask приложение само обработает редирект с / на telecom.kz
    }

    # Остальные location блоки для /admin/, /l/, etc.
    # Flask обработает их автоматически
}
```

## Шаг 5: Проверить конфигурацию и перезагрузить Nginx

```bash
# Проверить синтаксис конфигурации
sudo nginx -t

# Если проверка прошла успешно, перезагрузить Nginx
sudo systemctl reload nginx
# Или
sudo service nginx reload
```

## Шаг 6: Проверить работу

```bash
# Проверить редирект
curl -I https://b2c2.telecom.kz/

# Должен вернуть:
# HTTP/1.1 301 Moved Permanently
# Location: https://telecom.kz
```

## Альтернативный вариант: Редирект на уровне Nginx

Если вы хотите, чтобы редирект выполнялся на уровне Nginx (быстрее), можно настроить так:

```nginx
server {
    listen 443 ssl http2;
    server_name b2c2.telecom.kz;

    # SSL сертификаты
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Редирект корневого пути на telecom.kz
    location = / {
        return 301 https://telecom.kz;
    }

    # Проксирование остальных путей на Flask
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Важно:

- **НЕ** добавляйте редирект с `/` на `/admin/` в Nginx
- Flask приложение само обработает редирект с `/` на `telecom.kz` (код в `app.py`)
- Или настройте редирект в Nginx напрямую на `telecom.kz` (как показано выше)

