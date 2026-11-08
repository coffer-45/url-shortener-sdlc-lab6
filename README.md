# ЛР №6 — тестування вебсервісу скорочення URL

Навчальний моноліт Python/Django 5.2.18 з HTML-шаблонами та SQLite, продовження
ЛР №5. Репозиторій містить застосунок і автоматизовані тести трьох рівнів:
юніт-, компонентного й системного. Окремого REST/JSON API не передбачено:
браузер працює через HTTP-маршрути Django.

## Можливості та структура

Реєстрація, вхід і вихід; створення коротких посилань лише з HTTP/HTTPS-адрес,
унікальний код; публічний перехід із лічильником; перегляд і видалення лише
власних посилань; керування через Django Admin.

| Шлях | Призначення |
| --- | --- |
| `config/` | конфігурація Django, маршрути, WSGI |
| `links/models.py`, `links/migrations/` | модель посилання і SQLite-схема |
| `links/forms.py`, `links/services.py` | валідація, генерація коду, логіка перенаправлення |
| `links/views.py`, `links/admin.py`, `templates/` | HTTP-обробники, адмінпанель, HTML |
| `links/tests/test_unit_logic.py` | ізольовані юніт-тести |
| `links/tests/test_components.py`, `test_links.py` | компоненти, взаємодія, регресія |
| `links/tests/test_system.py`, `test_integration.py` | сценарії користувача |
| `scripts/system_probe.py`, `scripts/load_check.py` | реальний локальний HTTP, RSS, перезапуск, 20 клієнтів |
| `docs/testing.md` | план, результати, матриця FR/NFR, дефекти й рекомендації |

Ланцюг: браузер → Django views/Auth/форми → сервіси → ORM → SQLite.
Пряма залежність застосунку: `Django==5.2.18` у `requirements.txt`;
`requirements-test.txt` додає окрему тестову залежність `coverage==7.17.0`.

## Установлення, запуск і тести

Python 3.10+ та pip. Команди виконуйте з каталогу `url_shortener/`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

У браузері відкрийте `http://127.0.0.1:8000/register/`. Для адміністратора —
`.venv/bin/python manage.py createsuperuser` і `/admin/`.

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python -m coverage run --source=links -m manage test
.venv/bin/python -m coverage report --include='links/forms.py,links/models.py,links/services.py,links/views.py,links/admin.py' -m
.venv/bin/python scripts/system_probe.py
```

`system_probe.py` створює власну **тимчасову** SQLite-БД у `/tmp/opencode`,
запускає локальний сервер, тестує 20 сесій, вимірює RSS процесу через Linux
`/proc` і перевіряє коротке посилання після перезапуску. На Linux без
`/tmp/opencode` створіть каталог із правом запису. Скрипт не змінює локальну
`db.sqlite3` і не призначений для production. Результати можуть змінюватися
залежно від обладнання. `runserver` не використовують для реального розгортання.

## Підсумок перевірок

29/29 тестів; 100% покриття **операторів лише п'яти основних модулів** (110/110),
не всього Django чи всього репозиторію. Локально: 20 клієнтів, 180 запитів,
0 помилок; медіана 0,070 с, p95 0,753 с, максимум 1,237 с; RSS сервера до
навантаження 55 052 KiB, максимум 67 244 KiB (збільшення 12 192 KiB).
Збереження даних між локальними перезапусками перевірено. Точна матриця,
виявлені проблеми, обмеження і рекомендації — у [`docs/testing.md`](docs/testing.md).

Непідтверджені зовнішні вимоги: повний прогін у Chrome/Firefox/Edge, HTTPS
після розгортання та постійне сховище на хостингу. Локальний успіх NFR-01
не доводить продуктивності іншого сервера.

## Конфігурація production (не розгорталося)

`DJANGO_DEBUG=0`, надійний `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` із
реальним доменом, `DJANGO_DB_PATH` на постійному диску, TLS-проксі та WSGI.
`DJANGO_TRUST_PROXY_SSL=1` допустиме лише для проксі, який сам виставляє
`X-Forwarded-Proto` і видаляє значення клієнта. Після розгортання потрібні
`manage.py check --deploy`, резервне копіювання БД і ручний кросбраузерний
прогін. Див. також [`docs/integration.md`](docs/integration.md) із ЛР №5.
