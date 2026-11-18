# Система аренды строительных инструментов (микросервисы)

Учебное приложение на Flask. Система разделена на микросервисы **по бизнес-функциям**:
каждый сервис отвечает за свою предметную область, имеет собственную базу данных и REST API.

```
                    ┌────────── nginx :80 (шлюз) ──────────┐
   браузер ───────► │ /            → web                   │
                    │ /api/tools, /api/categories → tools  │
                    │ /api/customers   → customers         │
                    │ /api/rentals     → rentals           │
                    │ /api/maintenance → maintenance       │
                    └──────────────────────────────────────┘

 web ──HTTP──► tools · customers · rentals · maintenance      (интерфейс ходит только в API)
 rentals ──► tools, customers      (проверка: инструмент/клиент существуют, инструмент доступен)
 maintenance ──► tools             (проверка: инструмент существует)
 tools ──► rentals, maintenance    (нельзя удалить инструмент, на который есть ссылки)
 customers ──► rentals             (нельзя удалить клиента с арендами)
```

| Сервис | Ответственность | Данные (своя SQLite) | API |
|---|---|---|---|
| **tools** | каталог инструментов и категорий | `tools.db`: categories, tools | `/api/tools`, `/api/categories` |
| **customers** | клиенты | `customers.db`: customers | `/api/customers` |
| **rentals** | оформление аренды, статусы, стоимость | `rentals.db`: rentals | `/api/rentals` |
| **maintenance** | обслуживание и ремонт инструментов | `maintenance.db`: maintenance | `/api/maintenance` |
| **web** | HTML-интерфейс, своих данных нет | — | `/`, `/<сущность>`, `/status` |

Связи между сервисами — только по id и по HTTP, внешних ключей между базами нет.
У каждого сервиса есть `GET /health`.

## Бизнес-правила
- Аренда: дата окончания не раньше даты начала; инструмент и клиент должны существовать.
- Аренду (статусы «Забронирована», «Активна») нельзя оформить на инструмент, помеченный как недоступный.
- Один инструмент нельзя сдать двум клиентам на пересекающиеся даты (отменённые и завершённые аренды не мешают).
- Нельзя удалить инструмент, у которого есть аренды или записи обслуживания; нельзя удалить категорию с инструментами; нельзя удалить клиента с арендами.
- Если сосед недоступен, операция, которой он нужен, возвращает 503 (в интерфейсе — страница «Сервис временно недоступен»).

## REST API (пример)
Каждый ресурс: `GET /api/<res>` (параметры `q`, фильтры), `POST /api/<res>`, `GET|PUT|DELETE /api/<res>/<id>`, `GET /api/<res>/schema`.
Фильтры: tools — `category_id`, `available`; rentals — `tool_id`, `customer_id`, `status`; maintenance — `tool_id`.
```bash
curl -X POST http://localhost/api/customers -H "Content-Type: application/json" \
     -d '{"full_name": "Иван Иванов", "phone": "+7 900 000-00-00"}'
```
Ошибки приходят как `{"error": "..."}` с кодами 400 (валидация), 404, 409 (нарушено бизнес-правило), 503.

## Структура репозитория
```
common/            общий код: БД, валидация, ошибки, HTTP-клиент, типовой REST-ресурс
services/tools|customers|rentals|maintenance/   <имя>_app.py + Dockerfile
services/web/      web_app.py, templates/, static/, Dockerfile
nginx/             конфигурация шлюза для docker compose
k8s/               манифесты Kubernetes (по файлу на сервис)
scripts/split_monolith_db.py   перенос данных из старой rental.db
tests/             тесты сервисов и интерфейса, smoke_test.py для запущенной системы
run_local.py       запуск всей системы одной командой без Docker
Dockerfile.test    образ для прогона тестов (используется в Jenkins)
```

## Запуск без Docker
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python run_local.py
```
Откройте http://127.0.0.1:5000 (web). Сервисы: tools :5001, customers :5002, rentals :5003, maintenance :5004.
Базы создаются автоматически в `services/<имя>/instance/`; путь можно задать переменной `DATABASE`,
адреса соседей — переменными `TOOLS_URL`, `CUSTOMERS_URL`, `RENTALS_URL`, `MAINTENANCE_URL`.

## Запуск в Docker
```bash
docker compose up -d --build
```
Система доступна на http://localhost (nginx). Данные каждого сервиса — в своём томе (`tools-data` и т.д.).

## Миграция данных из монолита
Если есть старая база `instance/rental.db`:
```bash
python scripts/split_monolith_db.py instance/rental.db migrated/   # создаст 4 файла .db
```
Для запуска без Docker скопируйте файлы в `services/<имя>/instance/`. Для Docker скопируйте в тома, например:
`docker compose create && docker cp migrated/tools.db <контейнер tools>:/app/instance/tools.db`.

## Тесты
```bash
python -m pytest -v                                   # сервисы + интерфейс, сеть не нужна
BASE_URL=http://localhost python -m pytest tests/smoke_test.py   # дымовые тесты запущенной системы
```
Во время тестов вызовы между сервисами идут через Flask test client, у каждого сервиса временная БД.

## Jenkins и Kubernetes
`Jenkinsfile`: Checkout → тесты (`Dockerfile.test`) → сборка 5 образов → push в Docker Hub (ветка main) → `docker compose up -d --build` и проверка через nginx.
`k8s/`: `kubectl apply -f k8s/` — Deployment + Service (+ PVC для сервисов с SQLite) на каждый сервис, nginx — NodePort 30080.
Сервисы с SQLite запущены в одной реплике (`strategy: Recreate`): SQLite на ReadWriteOnce-томе нельзя масштабировать горизонтально — для масштабирования нужна PostgreSQL/MySQL.

## Важно для учебной демонстрации
Приложение учебное: нет аутентификации и CSRF-защиты (API через шлюз тоже открыт), перед реальным использованием это нужно добавить.
