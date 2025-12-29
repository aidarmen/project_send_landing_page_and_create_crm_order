#!/bin/bash
# Скрипт для разрешения конфликтов git на сервере

cd ~/projects/project_send_landing_page_and_create_crm_order

echo "=== Разрешение конфликтов Git ==="
echo ""

# Показать локальные изменения
echo "1. Локальные изменения:"
sudo git status

echo ""
echo "2. Различия в admin_views.py:"
sudo git diff admin_views.py | head -50

echo ""
echo "3. Различия в templates/admin/offer_form.html:"
sudo git diff templates/admin/offer_form.html | head -50

echo ""
echo "Выберите действие:"
echo "1) Сохранить локальные изменения (stash) и взять версию с GitHub"
echo "2) Отменить локальные изменения и взять версию с GitHub"
echo "3) Закоммитить локальные изменения"
echo ""
read -p "Ваш выбор (1/2/3): " choice

case $choice in
  1)
    echo ""
    echo "Сохраняю локальные изменения..."
    sudo git stash save "Local changes before pull $(date +%Y%m%d_%H%M%S)"
    
    echo ""
    echo "Получаю изменения с GitHub..."
    sudo git pull origin main
    
    echo ""
    echo "✅ Изменения получены!"
    echo "Локальные изменения сохранены в stash."
    echo "Для просмотра: sudo git stash list"
    echo "Для применения: sudo git stash pop"
    ;;
  2)
    echo ""
    echo "Отменяю локальные изменения..."
    sudo git checkout -- admin_views.py templates/admin/offer_form.html
    
    echo ""
    echo "Получаю изменения с GitHub..."
    sudo git pull origin main
    
    echo ""
    echo "✅ Изменения получены!"
    echo "Локальные изменения отменены."
    ;;
  3)
    echo ""
    echo "Закоммичу локальные изменения..."
    sudo git add admin_views.py templates/admin/offer_form.html
    sudo git commit -m "Local server changes $(date +%Y%m%d_%H%M%S)"
    
    echo ""
    echo "Попытка merge..."
    sudo git pull origin main
    
    if [ $? -ne 0 ]; then
      echo ""
      echo "⚠️  Конфликт при merge!"
      echo "Нужно разрешить конфликты вручную:"
      echo "1. Отредактируйте файлы с конфликтами"
      echo "2. sudo git add <файлы>"
      echo "3. sudo git commit"
    else
      echo ""
      echo "✅ Изменения успешно объединены!"
    fi
    ;;
  *)
    echo "Неверный выбор"
    exit 1
    ;;
esac

echo ""
echo "=== Готово! ==="

