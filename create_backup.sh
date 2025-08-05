#!/bin/bash

# Создание резервной копии сайта
echo "Создание резервной копии..."

# Создаем имя файла с датой
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_$TIMESTAMP"

# Создаем папку для резервных копий
mkdir -p backups

# Ищем базу данных в текущей директории и поддиректориях
DB_FILE=$(find . -name "english_teacher.db" -type f | head -1)

if [ -z "$DB_FILE" ]; then
    echo "Ошибка: база данных english_teacher.db не найдена!"
    exit 1
fi

echo "Найдена база данных: $DB_FILE"

# Копируем базу данных
cp "$DB_FILE" "backups/${BACKUP_NAME}.db"

# Проверяем, существует ли папка uploads
if [ -d "static/uploads" ]; then
    echo "Папка uploads найдена, добавляем в архив"
else
    echo "Папка uploads не найдена"
fi

# Создаем ZIP архив
if [ -d "static/uploads" ]; then
    zip -r "backups/${BACKUP_NAME}.zip" "backups/${BACKUP_NAME}.db" static/uploads
else
    zip "backups/${BACKUP_NAME}.zip" "backups/${BACKUP_NAME}.db"
fi

# Проверяем, создан ли архив
if [ ! -f "backups/${BACKUP_NAME}.zip" ]; then
    echo "Ошибка: не удалось создать архив!"
    exit 1
fi

# Удаляем временный файл базы данных
rm "backups/${BACKUP_NAME}.db"

echo "Резервная копия создана: backups/${BACKUP_NAME}.zip"
echo "Размер архива: $(du -h "backups/${BACKUP_NAME}.zip" | cut -f1)"

# Отправляем по email (если установлен mailutils)
if command -v mail &> /dev/null; then
    echo "Отправка резервной копии на email..."
    echo "Резервная копия сайта от $(date)" | mail -s "Backup $TIMESTAMP" -A "backups/${BACKUP_NAME}.zip" sal-olga@mail.ru
    echo "Резервная копия отправлена!"
else
    echo "Для отправки email установите mailutils: sudo apt install mailutils"
    echo "Или используйте команду: sudo apt install ssmtp mailutils"
fi
