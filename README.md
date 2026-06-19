# avar-me/ios

Сайт-промо + data-pipeline + публикуемые архивы словаря для iOS-приложения
**Аварский словарь** (аварско-русский и русско-аварский).

- Хостинг: **GitHub Pages**, домен `ios.avar.me` (CNAME), DNS в Cloudflare.
- `ios.avar.me` отдаёт промо-лендинг **и** endpoint обновлений: `latest.json` + `releases/*.zip`.
- iOS-приложение живёт в отдельном репозитории `avarme-ios`.

Полное описание архитектуры — в [`PLAN.md`](PLAN.md).

## Источники

Два независимо составленных словаря:

- `https://sources.avar.me/data/av-ru.jsonl` — аварско-русский (~22 855 записей)
- `https://sources.avar.me/data/ru-av.jsonl` — русско-аварский (~38 874 записей)

## Pipeline

Только Python 3.12, без внешних зависимостей (`sqlite3` — из stdlib).

```
download_sources.py   → data/*.jsonl
analyze_sources.py    → статистика (для quality gates)
build_dictionary.py   → build/dictionary.sqlite (+ metadata.json)
validate_dictionary.py→ quality gates
package_release.py    → public/releases/dictionary-vN.zip (+ checksum)
generate_latest.py    → public/latest.json
```

### Локальный запуск релиза

```bash
python scripts/download_sources.py
python scripts/build_dictionary.py --version 1 --notes "First release"
python scripts/validate_dictionary.py
python scripts/package_release.py --version 1
python scripts/generate_latest.py --version 1 --notes "First release"
```

### Тесты

```bash
python tests/test_normalization.py     # складывание палочки и пр.
```

## CI

`.github/workflows/build-and-publish.yml` — ручной запуск (`workflow_dispatch`)
с вводом `dictionary_version` и `release_notes`. Прогоняет тесты → весь
pipeline → коммитит `public/` (GitHub Pages раздаёт его как `ios.avar.me`).

## Формат словаря

`dictionary.sqlite` содержит оба словаря:

- `entries(id, dict, word, homonym, pos, data)` — `data` это полный JSON
  записи (senses, examples, see_also с резолвленными `target_id`).
- `search(lang, term, entry_id, weight)` — нормализованный индекс. `lang` =
  `av`|`ru` (письменность терма). Поиск: точное совпадение и префикс
  (`term GLOB 'q*'`, использует индекс).
  - `avarToRussian` → ищем `lang='av'`
  - `russianToAvar` → ищем `lang='ru'`
- `meta(key, value)` — то же, что в `metadata.json`.

Нормализация (`scripts/normalize.py`) должна совпадать с `TextNormalizer.swift`
в приложении. Ключевое правило: палочка `ӏ` и её заменители (`Ӏ 1 l I |`)
складываются в канон — и при индексации, и в пользовательском запросе.

## Откат релиза

Старые архивы не удаляются. Чтобы откатиться — перегенерировать `latest.json`
на предыдущую версию (или просто выпустить исправленную `vN+1`). См. PLAN.md §17.
