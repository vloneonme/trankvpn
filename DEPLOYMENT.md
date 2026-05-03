# 🚀 Развертывание на dev-nl1

## 📋 Структура на удаленном сервере

```
/opt/marzban/
├── Caddyfile
├── Caddyfile.old
├── docker-compose.yml
└── docker-compose.yml.base

/opt/ton-bot/
├── bot.py
├── Dockerfile
├── requirements.txt
├── .env (не в версионном контроле)
└── [NEW] README.md, CHANGELOG.md, и т.д.
```

## 🔄 Способ 1: Автоматическая синхронизация (через SCP)

### Шаг 1: Синхронизация файлов с локального машины

На локальной машине (где находится этот репозиторий):

```bash
cd /home/vlone/trankvpn
./sync-to-remote-scp.sh
```

Скрипт скопирует все файлы на сервер, новые конфиги будут с суффиксом `.new`.

### Шаг 2: Проверка и замена файлов на сервере

Подключитесь к серверу:

```bash
ssh zxc@dev-nl1
```

Проверьте скопированные файлы:

```bash
ls -lh /opt/marzban/*.new
ls -lh /opt/ton-bot/
```

Если всё выглядит хорошо, сделайте резервные копии и замените файлы:

```bash
# Для Marzban
cd /opt/marzban
cp Caddyfile Caddyfile.old
mv Caddyfile.new Caddyfile
cp docker-compose.yml docker-compose.yml.old.$(date +%s)
mv docker-compose.yml.new docker-compose.yml
```

### Шаг 3: Обновление .env файла

Bot нуждается в файле `.env`. Если он еще не создан:

```bash
cd /opt/ton-bot
cp .env.example .env
nano .env
# Отредактируйте с вашими параметрами
```

### Шаг 4: Перезагрузка сервисов

```bash
cd /opt/marzban
docker-compose down
docker-compose up -d

# Проверьте, что всё запустилось
docker-compose ps

# Смотрите логи бота
docker-compose logs -f bot
```

## 🔄 Способ 2: Ручная синхронизация через SCP

Если скрипт не работает, скопируйте файлы вручную:

### Bot файлы
```bash
# С локальной машины
scp ton-bot/bot.py zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/requirements.txt zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/Dockerfile zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/.env.example zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/README.md zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/CHANGELOG.md zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/SUMMARY.md zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/check-config.sh zxc@dev-nl1:/opt/ton-bot/
scp ton-bot/deploy.sh zxc@dev-nl1:/opt/ton-bot/

# Установить права
ssh zxc@dev-nl1 "chmod +x /opt/ton-bot/check-config.sh /opt/ton-bot/deploy.sh"
```

### Marzban файлы
```bash
scp marzban/Caddyfile zxc@dev-nl1:/opt/marzban/Caddyfile.new
scp marzban/docker-compose.yml zxc@dev-nl1:/opt/marzban/docker-compose.yml.new
```

## ✅ Проверка после развертывания

После перезагрузки проверьте:

```bash
# 1. Бот работает
docker-compose ps
# STATUS должен быть "Up"

# 2. Логи показывают успешный запуск
docker-compose logs bot | tail -20
# Ищите:
#   ✅ Подключение к БД установлено
#   ✅ Таблица bot_users готова
#   🚀 Запуск VPN бота

# 3. Бот отвечает на команды
docker-compose exec bot python -c "print('✅ Python работает')"

# 4. Проверьте конфигурацию
docker-compose exec -w /app bot bash /app/check-config.sh
```

## 🆘 Откат на предыдущую версию

Если что-то не работает:

```bash
cd /opt/marzban

# Верните старые файлы
cp Caddyfile.old Caddyfile
cp docker-compose.yml.old docker-compose.yml

# Перезагрузитесь
docker-compose down
docker-compose up -d

# Смотрите логи
docker-compose logs -f bot
```

## 📝 Отличия между старым и новым ботом

| Аспект | Старый | Новый |
|--------|--------|-------|
| Синтаксические ошибки | ❌ Есть ([3], [4]) | ✅ Исправлены |
| Логирование | Минимальное | Полное (файл + консоль) |
| Обработка ошибок | Плохая | Везде try-except |
| Тестовая подписка | Не работает | ✅ Работает |
| Платежи | Баги | ✅ Исправлены |
| Документация | Нет | ✅ 5 файлов |

## 🎯 Что дальше

После успешного развертывания:

1. **Протестируйте бота**:
   - Отправьте `/start` боту
   - Проверьте "Тестовый период"
   - Проверьте меню "Купить подписку"

2. **Мониторьте логи**:
   - `docker-compose logs -f bot` - следить за ошибками
   - `/var/log/bot/bot.log` - перманентные логи

3. **Обновляйте параметры**:
   - Цены в `.env` файле
   - Размеры тарифов
   - Описания продуктов

## 🆘 Если что-то не работает

### Проблема: "Ошибка при подключении к Marzban"
```bash
# Проверьте, что Marzban доступен
docker-compose ps | grep marzban
# Должен быть "Up"

# Проверьте .env файл
grep MARZBAN /opt/ton-bot/.env
```

### Проблема: "Ошибка при подключении к БД"
```bash
# Проверьте MariaDB
docker-compose ps | grep mariadb
# Должен быть "Up"

# Проверьте учетные данные в .env
grep DB_ /opt/ton-bot/.env
```

### Проблема: Логи не записываются
```bash
# Создайте директорию для логов
sudo mkdir -p /var/log/bot
sudo chmod 755 /var/log/bot

# Перезагрузите бота
docker-compose restart bot
```

## 📞 Контакт и поддержка

Если у вас возникли вопросы, проверьте:
1. [README.md](ton-bot/README.md) - подробная документация
2. [CHANGELOG.md](ton-bot/CHANGELOG.md) - что изменилось
3. [SUMMARY.md](ton-bot/SUMMARY.md) - краткая справка
