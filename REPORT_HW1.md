# Отчёт по домашнему заданию 1

Кредитный скоринг на German Credit: CatBoost в sklearn `Pipeline`, сервис на FastAPI,
логи в Postgres, Docker Compose и Kubernetes (kind). 

## 1. Тесты

`uv run pytest -v` при запущенном compose, чтобы выполнились и интеграционные тесты с базой:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/credit uv run pytest -v
```

Покрыто: контракт (422 на мусор, лишнее и пропущенное поле), smoke (диапазон `score` и типы ответа),
детерминизм (один вход дважды даёт один ответ), запись запроса в Postgres.

![pytest](docs/img/pytest.png)

## 2. Логи в Postgres (compose)

`bash scripts/compose.sh`: валидный запрос (200), невалидный (422) и `SELECT` из таблицы `predictions`.
Код ответа хранится в поле `status_code`; у отклонённых запросов `score` пустой.

![SELECT из таблицы логов](docs/img/select.png)

## 3. Kubernetes: две реплики и ответ модели через port-forward

`bash scripts/kind.sh`: `kubectl get pods` с двумя подами в `Running` и ответ `/v1/predict` через `kubectl port-forward`.

![get pods и predict](docs/img/kind.png)

## 4. k9s

![k9s](docs/img/k9s.png)

## Журнал проблем

### 1. `uv sync` не поставил основные зависимости

**Симптом:** в выводе `uv sync` были только pytest, ruff и locust, а fastapi, catboost и scikit-learn отсутствовали.

**Причина:** список `dependencies` в `[project]` был пустым.

**Как починил:** `uv add catboost scikit-learn pandas joblib fastapi uvicorn pydantic "psycopg[binary]"`.

### 2. `InconsistentVersionWarning` при загрузке модели

**Ошибка:**
```
InconsistentVersionWarning: Trying to unpickle estimator SimpleImputer from version 1.9.0 when using version 1.9.1
```

**Причина:** ноутбук обучения был запущен на ядре не из `.venv` проекта, и модель сохранилась другой версией scikit-learn.

**Как починил:** выбрал в VS Code ядро `HW1/.venv` и переобучил модель.

### 3. Сервис не стартует: нет `db.init`

**Ошибка:**
```
AttributeError: module 'credit_scoring.db' has no attribute 'init'
ERROR:    Application startup failed. Exiting.
```

**Причина:** файл `db.py` был пустым.

**Как починил:** добавил в `db.py` функции `init()` и `save_prediction()`.


### 4. Логи не появлялись в Postgres

`SELECT` из `predictions` возвращал 0 строк, хотя запросы через проходили с кодом 200.

**Причина:** запросы уходили в контейнер `credit-scoring:1.0`, запущенный ранее через `docker run` без `DATABASE_URL`, а не в локальный uvicorn с базой.

**Как починил:** `docker ps` → `docker stop <контейнер>`, перезапустил локальный сервис.

### 5 Отчёт по домашнему заданию 1

Кредитный скоринг на German Credit: CatBoost в sklearn `Pipeline`, сервис на FastAPI,
логи в Postgres, Docker Compose и Kubernetes (kind). Все проверки ниже сняты
на свежем клоне репозитория командами из README.

