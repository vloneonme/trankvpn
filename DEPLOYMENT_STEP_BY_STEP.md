# 🚀 ИНСТРУКЦИЯ ПО РАЗВЕРТЫВАНИЮ НА dev-nl1

## ✅ ЧТО БЫЛО СДЕЛАНО

Все файлы скопированы на сервер во временную директорию:
```
/tmp/trankvpn_update/
```

## 📋 ЧТО ДАЛЬШЕ (выполнить на сервере dev-nl1)

### Шаг 1: Подключитесь к серверу

```bash
ssh zxc@dev-nl1
```

### Шаг 2: Проверьте скопированные файлы

```bash
ls -lh /tmp/trankvpn_update/
```

Вы должны увидеть:
- bot.py
- requirements.txt
- Dockerfile
- .env.example
- README.md
- CHANGELOG.md
- SUMMARY.md
- check-config.sh
- deploy.sh
- Caddyfile
- docker-compose.yml

### Шаг 3: Установите права на скрипты

```bash
sudo chmod +x /tmp/trankvpn_update/check-config.sh /tmp/trankvpn_update/deploy.sh
```

### Шаг 4: Скопируйте файлы БОТ

```bash
sudo cp /tmp/trankvpn_update/bot.py /opt/ton-bot/
sudo cp /tmp/trankvpn_update/requirements.txt /opt/ton-bot/
sudo cp /tmp/trankvpn_update/Dockerfile /opt/ton-bot/
sudo cp /tmp/trankvpn_update/.env.example /opt/ton-bot/
sudo cp /tmp/trankvpn_update/README.md /opt/ton-bot/
sudo cp /tmp/trankvpn_update/CHANGELOG.md /opt/ton-bot/
sudo cp /tmp/trankvpn_update/SUMMARY.md /opt/ton-bot/
sudo cp /tmp/trankvpn_update/check-config.sh /opt/ton-bot/
sudo cp /tmp/trankvpn_update/deploy.sh /opt/ton-bot/
sudo chmod +x /opt/ton-bot/check-config.sh /opt/ton-bot/deploy.sh
```

### Шаг 5: Обновите конфиги MARZBAN

```bash
cd /opt/marzban

# Создайте резервные копии
sudo cp Caddyfile Caddyfile.backup.$(date +%s)
sudo cp docker-compose.yml docker-compose.yml.backup.$(date +%s)

# Скопируйте новые файлы
sudo cp /tmp/trankvpn_update/Caddyfile .
sudo cp /tmp/trankvpn_update/docker-compose.yml .
```

### Шаг 6: Проверьте/обновите .env (если нужно)

```bash
# Проверьте, что .env существует
ls -l /opt/ton-bot/.env

# Если не существует, создайте из примера
if [ ! -f /opt/ton-bot/.env ]; then
    sudo cp /opt/ton-bot/.env.example /opt/ton-bot/.env
fi

# Отредактируйте (если нужно)
sudo nano /opt/ton-bot/.env
```

### Шаг 7: Пересоберите и перезагрузите сервисы

```bash
cd /opt/marzban

# Остановите текущие сервисы
sudo docker-compose down

# Пересоберите Docker образы (т.к. Dockerfile изменился)
sudo docker-compose build

# Запустите сервисы
sudo docker-compose up -d

# Проверьте, что всё запустилось
sudo docker-compose ps
```

Вывод должен показать все сервисы как "Up":
```
NAME                COMMAND                  SERVICE             STATUS
marzban             "/entrypoint.sh"         marzban             Up 2 minutes
caddy               "caddy run --config…"    caddy               Up 2 minutes
bot                 "python bot.py"          bot                 Up 2 minutes
mariadb             "docker-entrypoint.s…"   mariadb             Up 2 minutes
```

### Шаг 8: Проверьте логи БОТ

```bash
# Смотрите последние логи
sudo docker-compose logs bot | tail -20

# Или следите в реальном времени
sudo docker-compose logs -f bot
```

В логах должны быть строки:
```
✅ Подключение к БД установлено
✅ Таблица bot_users готова
✅ Токен Marzban получен
🚀 Запуск VPN бота...
```

## 🧪 Протестируйте БОТ

После успешного запуска:

1. **Отправьте команду `/start` боту** - должна открыться главная клавиатура
2. **Нажмите "🎁 Тестовый период"** - должна выдаться тестовая подписка
3. **Нажмите "💳 Купить подписку"** - должны отобразиться тарифы
4. **Нажмите "ℹ️ О сервисе"** - должна показаться информация о сервисе

## 🧹 Очистка

После успешного развертывания удалите временные файлы:

```bash
rm -rf /tmp/trankvpn_update
```

## 🆘 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Проверьте логи
```bash
sudo docker-compose logs bot | tail -50
```

### Перезагрузите БОТ контейнер
```bash
sudo docker-compose restart bot
```

### Проверьте конфигурацию
```bash
cat /opt/ton-bot/.env
```

### Проверьте доступность Marzban
```bash
curl http://localhost:8000/api/admin/token
```

### Проверьте доступность БД
```bash
docker-compose exec mariadb mysql -u marzban -p -e "SELECT 1"
```

## 📊 ОТКАТ НА СТАРУЮ ВЕРСИЮ

Если нужно вернуться на старую версию:

```bash
cd /opt/marzban

# Восстановите старые файлы
sudo cp Caddyfile.backup.* Caddyfile
sudo cp docker-compose.yml.backup.* docker-compose.yml

# Перезагрузитесь
sudo docker-compose down
sudo docker-compose up -d

# Смотрите логи
sudo docker-compose logs -f bot
```

## 📝 ВАЖНЫЕ ФАЙЛЫ

После развертывания вы получили:

- **/opt/ton-bot/README.md** - полная документация по боту
- **/opt/ton-bot/CHANGELOG.md** - что изменилось
- **/opt/ton-bot/SUMMARY.md** - краткая справка
- **/opt/ton-bot/.env.example** - шаблон конфигурации
- **/opt/ton-bot/check-config.sh** - проверка конфигурации
- **/opt/ton-bot/deploy.sh** - автоматическое развертывание

## ✅ ЧЕКЛИСТ

- [ ] Подключен к серверу dev-nl1
- [ ] Скопированы все файлы БОТ в /opt/ton-bot/
- [ ] Обновлены конфиги MARZBAN (Caddyfile, docker-compose.yml)
- [ ] Установлены права на скрипты
- [ ] .env файл заполнен правильно
- [ ] Пересоздано docker образы (`docker-compose build`)
- [ ] Перезагружены сервисы (`docker-compose down && docker-compose up -d`)
- [ ] Проверены логи БОТ
- [ ] Протестирована команда `/start`
- [ ] Удалены временные файлы (`rm -rf /tmp/trankvpn_update`)

## 🎉 ВСЁ ГОТОВО!

Ваш VPN бот успешно развернут и готов к работе!

### Дальнейший мониторинг

Регулярно проверяйте логи:
```bash
sudo docker-compose logs -f bot
```

И статус сервисов:
```bash
sudo docker-compose ps
```
