# Исправления ошибок в логах

## 1. Ошибка логирования бота (FileNotFoundError)

**Проблема:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/var/log/bot/bot.log'
```

**Причина:** Директория `/var/log/bot` не существовала или не была доступна для записи внутри контейнера.

**Решение в файле `/workspace/ton-bot/bot.py`:**
- Добавлена проверка существования директории после попытки создания
- Добавлена проверка прав доступа через создание тестового файла
- Использован параметр `delay=True` в `logging.FileHandler()` для отложенного открытия файла
- Улучшена обработка fallback на текущую директорию при ошибках

## 2. Ошибка валидации Marzban API (ResponseValidationError)

**Проблема:**
```
fastapi.exceptions.ResponseValidationError: 1 validation errors:
{'type': 'value_error', 'loc': ('response', 'users', 9, 'proxies'), 'msg': 'Value error, Each user needs at least one proxy', 'input': [], 'ctx': {'error': ValueError('Each user needs at least one proxy')}}
```

**Причина:** При создании пользователя в Marzban поле `proxies` было задано неполно. Для VLESS прокси требуется указать как минимум `flow` и `id`.

**Решение в файле `/workspace/ton-bot/bot.py`:**
Изменена структура данных `user_data` в функции `create_vpn_user()`:
```python
# Было:
"proxies": {"vless": {"flow": "xtls-rprx-vision"}}

# Стало:
"proxies": {"vless": {"flow": "xtls-rprx-vision", "id": ""}}
```

Пустой `id` будет автоматически сгенерирован Marzban при создании пользователя.

## 3. Ошибка подключения Caddy к сокету Marzban

**Проблема:**
```
dial unix /var/lib/marzban/marzban.socket: connect: no such file or directory
```

**Причина:** Сокет Marzban не был создан или путь к нему неверен.

**Возможные решения:**
1. Убедиться, что Marzban успешно запустился и создал сокет
2. Проверить, что том `/var/lib/marzban` правильно примонтирован в оба контейнера (marzban и caddy)
3. Проверить права доступа к сокету

**Проверка конфигурации:**
- В `docker-compose.yml` оба сервиса (marzban и caddy) имеют доступ к тому `/var/lib/marzban`
- В `Caddyfile` указан правильный путь: `unix//var/lib/marzban/marzban.socket`
- В `.env` файлe Marzban настроен на использование сокета: `UVICORN_UDS = "/var/lib/marzban/marzban.socket"`

**Рекомендуемые действия на сервере:**
```bash
# Перезапустить сервисы
cd /opt/marzban
docker-compose down
docker-compose up -d

# Проверить логи Marzban
docker-compose logs marzban

# Проверить наличие сокета
ls -la /var/lib/marzban/marzban.socket
```

## Файлы, которые были изменены:

1. `/workspace/ton-bot/bot.py` - исправлены ошибки логирования и структуры proxies
