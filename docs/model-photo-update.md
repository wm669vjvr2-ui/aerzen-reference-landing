# Фото всех моделей: проверка изменения

15.10.2026. Изменение выполнено только в отдельном aerzen-reference-landing, ветка codex/reference-landing. Существующая чёрно-жёлтая система сохранена; применён focused workflow UI Pattern Forge без нового выбора концептов.

Фотографиями покрыты все 30 позиций: 7 AERZEN, 11 HUADONG HDSR, 6 MINGTIAN RSR и 6 ERSTVAK ERB. Это 7 разных основных фотографий и 7 дополнительных видов, а не 30 подтверждённых снимков конкретных SKU. Там, где первичный источник даёт только общий вид серии, интерфейс явно сохраняет эту подпись. Фото появились в каталоге, карточках моделей, на главной в категориях, в справочнике и каждой строке технических таблиц.

Источники и условия доступа:

- AERZEN: официальные страницы [Delta Blower](https://www.aerzen.com/us/products/product/blower-units-delta-blower-generation-5), [Delta Hybrid](https://www.aerzen.com/us/products/product/screw-blowers-delta-hybrid), [Delta Screw](https://www.aerzen.com/product/screw-compressor-units-delta-screw-with-direct-drive), [GM](https://www.aerzen.com/product/positive-displacement-blower-stages). Детали: model-photo-sources-aerzen.md и aerzen-photo-manifest.json.
- Китайские: [HUADONG HDSR](https://www.huadongblower.com/products_detail.php?cid=6&id=1), [MINGTIAN RSR](https://www.rootsblowertech.com/rsr-roots-blower/). Детали: model-photo-sources-chinese.md и model-photo-manifest-chinese.json.
- ERB: официальная [серия ERB](https://erstvak.com/brands/rotornye-vozdukhoduvki-erstevak/erstevak-seriya-erb/) и шесть карточек. Детали: model-photo-sources-erb.md и model-photo-manifest-erb.json.

Доступ к исходным страницам и файлам открыт; лицензия на коммерческое перераспространение не установлена. Фотографии производителей используются в локальной версии по поручению пользователя; перед публичной публикацией нужны разрешение или замена. Это отдельно от ранее добавленных тематических фотографий Unsplash с проверенной бесплатной лицензией.

Использован собственный минимальный компонент figure/img/figcaption с object-fit:contain и native details для дополнительных видов. Его код в templates/_macros.html и static/css/model-photos.css. Новые UI-пакеты и внешние шрифты не устанавливались. Для небольшой правки сохранены прежние исследованные источники и ограничения 21st; выполнена локальная UX-проверка доступности/масштабирования/веса фотографий. Атрибуты alt/width/height, lazy loading второстепенных фото, видимый фокус и reduced-motion базового стиля сохранены.

| Требование | Статус | Доказательство / ограничение |
| --- | --- | --- |
| Фото всех моделей | готово | 30 записей с реальными локальными файлами, проверенными SHA-256, размерами и декодированием. Подписи отличают серию от точного SKU. |
| Страницы / ресурсы | готово | 13 страниц с фото дают 200; все указанные изображения дают 200, имеют alt и размеры. |
| Адаптивность | готово | 24 браузерных сценария: восемь страниц на 390/768/1440px; переполнения body и битых загруженных фото нет. |
| Клавиатура / галерея | готово | Дополнительные виды Delta Blower открываются и закрываются Enter; семантика native details. Новых диалогов нет. |
| Регрессии | готово | 38 tests passed, одно прежнее предупреждение Starlette/httpx; git diff --check чистый. Приём заявок, цены и commerce-ограничения не изменялись. |
| Браузерные ошибки | готово | Новых console errors/warnings в заключительных сценариях нет. |
| Данные / cookies / зависимости | не применимо | Новых внешних запросов из страницы, трекеров, форм, хранилищ и зависимостей не добавлено; изображения отдаются локально. |
| Публичная публикация | заблокировано | Права на коммерческое распространение новых фото производителей не подтверждены; прежние hosting/owner/privacy блокеры также сохраняются. |

Изменённые файлы: content/products.json, content/alternatives.json, templates/_macros.html, product.html, models.html, index.html, alternative.html, alternatives.html, base.html; добавлены static/css/model-photos.css и static/images/models/. Python/FastAPI/Jinja/SQLite сохранены. Оригинальный aerzen-site не изменялся.
