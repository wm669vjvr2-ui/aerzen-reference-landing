# Каталог HDSR, RSR и ERB и удаление пометки

15.10.2026. Работа только в отдельном `aerzen-reference-landing`, ветка `codex/reference-landing`. Исходный `aerzen-site` и его remote не изменялись. Python/FastAPI/Jinja2/SQLite и выбранный чёрно-жёлтый стиль сохранены.

С главной, справочника, страниц серий и поиска убрана крупная плашка и фраза «Эти модели не поставляем». Вместо плашки остаётся обычное пояснение о техническом сравнении и подборе AERZEN. Это не добавляет подтверждённое наличие, цены, товарные SKU или предложения продажи HDSR/RSR/ERB.

На главной HDSR/RSR/ERB показаны в первом экране с реальным фото и тремя карточками серий сразу после преимуществ. Общий `/models` содержит все 30 позиций: сначала 11 HDSR, 6 RSR и 6 ERB, затем семь AERZEN. У каждой позиции есть фото, характеристики и ссылка. Фото серии подписаны как примеры исполнения; 30 позиций не означают 30 уникальных фото конкретных SKU. ERB не назван китайским без подтверждения происхождения.

GET-фильтры: поиск до 100 символов, производитель (`huadong`, `mingtian`, `erstvak`, `aerzen`), тип и категория. Они работают вместе и без JavaScript. Карточки справочных моделей ведут к соответствующим строкам таблиц. Данные справочника остаются отдельно от products, корзины, прайсового фида и product_slug заявок.

## Источники и компоненты

Применён focused workflow `ui-pattern-forge:compose-ui-patterns` в уже выбранной системе. Локальная UX-рекомендация UI UX Pro Max: `industrial catalogue brand filter model search product photos`, домен `ux`; сохранены видимые подписи, сброс и осмысленное пустое состояние. Использованы собственные минимальные карточки и стандартные HTML `select`, `figure`, `img`, `figcaption`, `details`/`dialog`. Компоненты: `templates/models.html`, `templates/_macros.html`; стили: `static/css/storefront.css`, `model-photos.css`, `reference-focus.css`. Сторонние UI-пакеты не добавлялись. Предыдущие Refero/21st источники и ограничения: [reference-evidence.md](reference-evidence.md); MCP 21st недоступен, чужой компонентный код не импортирован.

Фотографии взяты из ранее проверенных официальных страниц [HUADONG HDSR](https://www.huadongblower.com/products_detail.php?cid=6&id=1), [MINGTIAN RSR](https://www.rootsblowertech.com/rsr-roots-blower/), [ERSTVAK ERB](https://erstvak.com/brands/rotornye-vozdukhoduvki-erstevak/erstevak-seriya-erb/) и AERZEN. Точные файлы, SHA-256, подписи, источники и ограничения: [model-photo-update.md](model-photo-update.md) и указанные там манифесты. Новых фото или прав на их распространение этим изменением не заявлено. Открытый доступ к странице производителя не подтверждает лицензию на коммерческую публикацию.

## Проверка

| Требование | Статус | Доказательство / ограничение |
| --- | --- | --- |
| Пометка удалена | готово | HTTP-проверка шести страниц и браузерный скриншот справочника; `.supply-disclosure` и прежней фразы нет. |
| Общий каталог и фото | готово | 30 карточек, 23 справочные первыми; в HTML каталога 30 img с alt/width/height. 14 уникальных фото на шести проверенных страницах возвращают HTTP 200. |
| Фильтры и переходы | готово | Все комбинации покрыты тестами; в браузере выбор ERSTVAK даёт 6 моделей, поиск HDSR150 — одну; ссылка ERB-50 ведёт к правильному якорю. |
| Мобильная версия | готово | 12 сценариев: главная, каталог, справочник и ERB на 390/768/1440 px. Ширина body равна viewport, битых загруженных изображений нет. Данные: `previews/catalog-focus-responsive.json`. |
| Клавиатура и браузер | готово | Фильтр отправляется Enter; быстрый поиск закрывается Escape с возвратом фокуса. Console errors/warnings отсутствуют. |
| Код и границы данных | готово | 52 tests passed, compileall и git diff --check. Справочные модели отвергаются как product_slug/SKU; Product/Offer и переходов на основной сайт нет. Одно прежнее предупреждение Starlette/httpx. |
| Новые данные, cookies, платежи, обработчики | не применимо | Изменены только представление и GET-фильтрация; секреты, БД, формы, commerce, аналитика и зависимости не менялись. |
| GitHub: private | готово | Проверено 15.10.2026 через `gh api repos/wm669vjvr2-ui/aerzen-reference-landing`: private=true, visibility=private. |
| Публичный HTTPS | заблокировано | Совместимый Python-хостинг не настроен; права на публикацию фото производителей и прежние owner/privacy/real-lead настройки не подтверждены. Локальная версия не объявляется production. |

Изменённые файлы: `app/main.py`, `templates/models.html`, `index.html`, `base.html`, `about.html`, `alternative.html`, `alternatives.html`, новый `static/css/reference-focus.css`, `tests/test_storefront.py`, `tests/test_alternatives.py`, README и документы выбранной системы.

Скриншоты: `previews/catalog-focus-no-notice.png`, `catalog-focus-home-desktop.png`, `catalog-focus-cards-desktop.png`, `catalog-focus-mobile.png`. Локальный просмотр: http://127.0.0.1:8027/models. Дополнительный отчёт HTTP: `previews/catalog-focus-http.json`.
