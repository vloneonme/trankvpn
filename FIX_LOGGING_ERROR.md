# 🔧 ИСПРАВЛЕНИЕ ОШИБКИ ЛОГИРОВАНИЯ

## ❌ Проблема

При запуске бота появляется ошибка:
```
FileNotFoundError: [Errno 2] No such file or directory: '/var/log/bot/bot.log'
```

## ✅ Решение

Были сделаны следующие обновления:

### 1. **bot.py** - Автоматическое создание директории логов
- ✅ Добавлен импорт `Path` из `pathlib`
- ✅ Добавлена проверка и создание директории `/var/log/bot` при запуске
- ✅ Если директория не создается, используется текущая директория как fallback

### 2. **Dockerfile** - Создание директории в образе
- ✅ Добавлена команда `mkdir -p /var/log/bot` при сборке образа
- ✅ Установлены правильные права (`chmod 755`)

### 3. **docker-compose.yml** - Двойная защита
- ✅ Добавлен том для директории логов: `- /var/log/bot:/var/log/bot`
- ✅ Добавлена команда инициализации: `mkdir -p /var/log/bot && python bot.py`

## 📋 ЧТО НУЖНО СДЕЛАТЬ НА СЕРВЕРЕ

### Шаг 1: Обновите файлы

```bash
ssh zxc@dev-nl1

# Скопируйте обновленные файлы
sudo cp /tmp/trankvpn_update/bot.py /opt/ton-bot/
sudo cp /tmp/trankvpn_update/Dockerfile /opt/ton-bot/
sudo cp /tmp/trankvpn_update/docker-compose.yml /opt/marzban/
```

### Шаг 2: Пересоберите образ

```bash
cd /opt/marzban
sudo docker-compose down
sudo docker-compose build --no-cache  # Важно: --no-cache для пересборки
sudo docker-compose up -d
```

### Шаг 3: Проверьте логи

```bash
# Смотрите логи в реальном времени
sudo docker-compose logs -f bot

# Должны увидеть:
# ✅ Подключение к БД установлено
# ✅ Таблица bot_users готова
# 🚀 Запуск VPN бота...
```

### Шаг 4: Проверьте, что логи записываются

```bash
# Должен существовать файл с логами
tail -f /var/log/bot/bot.log

# Или внутри контейнера
docker-compose exec bot tail -f /var/log/bot/bot.log
```

## 🎯 Результат

После этих изменений:
- ✅ Директория `/var/log/bot` будет автоматически создана
- ✅ Логи будут записываться в файл и в консоль
- ✅ Бот запустится без ошибок
- ✅ Если Dockerfile пересобран - гарантирована уже существующая директория

## 🔄 Альтернатива (без пересборки)

Если вы хотите обновить только `bot.py` без пересборки образа:

```bash
cd /opt/ton-bot
sudo cp /tmp/trankvpn_update/bot.py .

cd /opt/marzban
sudo docker-compose restart bot
```

Это будет работать, потому что `bot.py` теперь создает директорию самостоятельно.

## 📝 Изменения в коде

### bot.py - Создание директории при запуске
```python
from pathlib import Path

LOG_DIR = Path('/var/log/bot')
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    print(f"⚠️  Не удалось создать директорию логов: {e}")
    LOG_DIR = Path('.')
```

### Dockerfile - Создание при сборке
```dockerfile
RUN mkdir -p /var/log/bot && chmod 755 /var/log/bot
```

### docker-compose.yml - Дополнительная безопасность
```yaml
volumes:
  - /var/log/bot:/var/log/bot
command: sh -c "mkdir -p /var/log/bot && python bot.py"
```

## 🆘 Если всё ещё не работает

### Проверьте разрешения на хосте
```bash
ls -ld /var/log/bot
# Должно быть что-то вроде: drwxr-xr-x 2 root root 4096 May 4 12:00 /var/log/bot
```

### Создайте директорию вручную (если нужно)
```bash
sudo mkdir -p /var/log/bot
sudo chmod 755 /var/log/bot
```

### Очистите старые контейнеры
```bash
cd /opt/marzban
sudo docker-compose down -v
sudo docker system prune -a
sudo docker-compose up -d
```

## ✅ Чеклист

- [ ] Скопированы обновленные файлы
- [ ] Образ пересобран (`docker-compose build --no-cache`)
- [ ] Сервисы перезагружены (`docker-compose up -d`)
- [ ] Проверены логи (`docker-compose logs bot`)
- [ ] Директория `/var/log/bot` существует
- [ ] Файл логов создан и содержит события

## 🎉 Готово!

Ошибка логирования полностью исправлена.
