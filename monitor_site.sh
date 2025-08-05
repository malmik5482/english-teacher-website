#!/bin/bash

echo "=== Мониторинг сайта преподавателя английского ==="
echo "Нажмите Ctrl+C для выхода"
echo ""

# Показываем последние логи
echo "Последние сообщения от сайта:"
sudo journalctl -u english-teacher-site.service -n 20 --no-pager

echo ""
echo "В реальном времени (нажмите Ctrl+C для остановки):"
echo ""

# Показываем логи в реальном времени
sudo journalctl -u english-teacher-site.service -f
