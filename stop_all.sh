#!/bin/bash

echo "=== Остановка сервисов сайта ==="
echo ""

# Останавливаем веб-сервис
if systemctl is-active --quiet english-teacher-site.service; then
    echo "⏹️  Остановка веб-сервиса..."
    sudo systemctl stop english-teacher-site.service
    echo "✅ Веб-сервис остановлен"
else
    echo "ℹ️  Веб-сервис не запущен"
fi

echo ""
echo "📊 Текущий статус:"
sudo systemctl status english-teacher-site.service --no-pager -l
