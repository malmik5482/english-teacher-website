#!/bin/bash

echo "=== Запуск всех сервисов сайта ==="
echo ""

# Проверяем, запущен ли сервис
if systemctl is-active --quiet english-teacher-site.service; then
    echo "✅ Веб-сервис уже запущен"
else
    echo "🚀 Запуск веб-сервиса..."
    sudo systemctl start english-teacher-site.service
    sleep 2
fi

# Проверяем статус
echo ""
echo "📊 Статус сервисов:"
sudo systemctl status english-teacher-site.service --no-pager -l

echo ""
echo "🌐 Сайт доступен по адресам:"
echo "   http://localhost:5000"
echo "   http://$(hostname -I | awk '{print $1}'):5000"

echo ""
echo "📂 Резервные копии сохраняются в:"
echo "   /home/misha/english_teacher_site/backups/"

echo ""
echo "📅 Автоматическое резервное копирование:"
echo "   Ежедневно в 02:00"

echo ""
echo "📋 Для просмотра логов в реальном времени выполните:"
echo "   ./monitor_site.sh"
