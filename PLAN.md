# Avar Dictionary iOS App — PLAN.md

Аварско-Русский и Русско-Аварский словарь для iPhone и iPad.

Проект должен работать полностью офлайн, но уметь периодически обновлять словарные данные с `https://ios.avar.me`.

---

# 1. Общая идея

У нас есть **два** исходных словаря:

- `https://sources.avar.me/data/av-ru.jsonl` — аварско-русский (~22 855 записей)
- `https://sources.avar.me/data/ru-av.jsonl` — русско-аварский (~38 874 записей)
- веб-представление: `https://dev.avar.me`

Это **два независимо составленных словаря**, а не зеркала друг друга. Оба попадают в один релизный пакет.

Приложение iOS не должно напрямую зависеть от `sources.avar.me`.

Вместо этого нужен отдельный build pipeline:

```text
sources.avar.me (av-ru.jsonl + ru-av.jsonl)
      ↓
GitHub Actions manual build
      ↓
prepare iOS dictionary package
      ↓
GitHub Pages (репозиторий avar-me/ios)
      ↓
https://ios.avar.me   (промо-лендинг + /latest.json + /releases/*.zip)
      ↓
iOS app downloads new dictionary archive
```

То есть:

- `sources.avar.me` — источник сырья;
- `ios.avar.me` — одновременно промо-сайт приложения (лендинг, QR-код на App Store) **и** стабильный production-endpoint, отдающий архивы словаря;
- iOS-приложение скачивает только готовые релизы словаря;
- обновления словаря не требуют обновления приложения через App Store.

## Репозитории

- **`avar-me/ios`** (`git@github.com:avar-me/ios.git`, эта папка) — сайт-промо + data-pipeline + публикуемые архивы. Хостинг: **GitHub Pages**; домен `ios.avar.me` через CNAME, **DNS `avar.me` управляется в Cloudflare**.
- **`../avarme-ios`** — отдельный репозиторий SwiftUI-приложения.

---

# 2. Главные принципы

## 2.1. Приложение должно работать офлайн

Внутри первой версии приложения должен быть встроенный словарь.

Если интернета нет, приложение всё равно работает.

## 2.2. Обновлять словарь целиком

Не надо делать патчи по словам.

Обновляем целый архив словаря:

```text
dictionary-v43.zip
```

Почему:

- проще код;
- меньше ошибок;
- не нужны миграции;
- проще откатиться;
- проще тестировать;
- 25–100 тысяч слов — это небольшой объём данных для iPhone.

## 2.3. iOS app не строит индексы

Все тяжёлые операции делаются в build pipeline.

Приложение получает уже готовые файлы:

```text
dictionary.json
av_index.json
ru_index.json
metadata.json
```

или один файл:

```text
dictionary.sqlite
```

**Рекомендуемый вариант: SQLite + FTS5 уже в MVP.**

Объём (~61 700 записей суммарно, ~26 MB исходного JSONL) и необходимость префиксного/подстрочного поиска по нескольким полям делают парсинг большого `dictionary.json` в память на запуске медленным на старых устройствах. SQLite + FTS5 даёт быстрый поиск и нормализацию «из коробки».

```text
dictionary.sqlite
metadata.json
```

JSON-файлы (`dictionary.json`, `av_index.json`, `ru_index.json`) остаются только как промежуточный формат внутри pipeline и для отладки/валидации.

---

# 3. Архитектура данных

## 3.1. Исходные файлы

Источники (оба обязательны):

```text
https://sources.avar.me/data/av-ru.jsonl   (аварско-русский)
https://sources.avar.me/data/ru-av.jsonl   (русско-аварский)
```

Формат: JSONL, одна словарная запись на строку.

**Реальная структура записи** (изучена по данным, отличается от ранних набросков — плоского `translations` НЕТ):

```json
{
  "word": "аб",
  "stress": 1,
  "stem": "а",
  "homonym": 2,
  "forms": ["аб", "алъ", "алъул", "ал"],
  "pos": "местоимение",
  "form": "именительный",
  "gender_forms": { },
  "labels": [],
  "senses": [
    {
      "text": "это, этот, эта",
      "precomment": "...",
      "comment": "только",
      "labels": ["местоимение", "указательное местоимение"],
      "examples": [
        {"av": "аб дир къалам буго", "ru": "это мой карандаш", "labels": [], "comment": ""}
      ],
      "masdarfrom": "...", "genitivefrom": "...", "pluralfor": "...",
      "forceto": "...", "participlefrom": "...", "refwordnum": 1
    }
  ],
  "see_also": [{"target": "гьаб", "kind": "see"}]
}
```

### Важные особенности данных

- Перевод/толкование лежит в **`senses[].text`** (у записи может быть несколько senses), а не в `translations`.
- Примеры — массив `examples` с полями `av`, `ru`, `labels`, `comment`.
- **Записи без `senses`** (836 в av-ru, 3449 в ru-av) и **senses без `text`** (6230 в av-ru) — это легитимные грамматические заглушки-формы, ссылающиеся через `see_also` / `*from` на основную статью. Их **нельзя** отбраковывать как «пустые».
- `homonym` — одно слово может встречаться несколько раз (506 повторов в av-ru). Влияет на генерацию ID.
- `see_also.kind` принимает значения `see` / `from`. Грамматические связи: `masdarfrom`, `genitivefrom`, `pluralfor`, `masdarforceto`, `forceto`, `participlefrom`, `dativefrom`, `ergativefrom`, `deverbfrom`, `locativefrom`, `ablativefrom`, `casefrom`, `refwordnum`, `link_helper`.
- На этапе сборки `see_also.target` и `*from`-ссылки нужно **резолвить в стабильные ID**, чтобы приложение строило переходы между статьями.

> Семантика редких полей (`precomment`, `masdarforceto`, `forceto`, `refwordnum`, `link_helper`, `deverbfrom`) требует уточнения у владельца данных.

---

# 4. Формат iOS-релиза

Каждый релиз словаря должен публиковаться на `https://ios.avar.me`.

Предлагаемая структура:

```text
ios.avar.me/
├── latest.json
├── releases/
│   ├── dictionary-v1.zip
│   ├── dictionary-v2.zip
│   └── dictionary-v3.zip
└── checksums/
    ├── dictionary-v1.sha256
    ├── dictionary-v2.sha256
    └── dictionary-v3.sha256
```

---

# 5. latest.json

Файл `latest.json` — главный файл, который проверяет iOS-приложение.

Пример:

```json
{
  "schema_version": 1,
  "dictionary_version": 43,
  "build_id": "2026-06-19T21-30-00Z",
  "sources": [
    {"name": "av-ru", "url": "https://sources.avar.me/data/av-ru.jsonl", "sha256": "abc123..."},
    {"name": "ru-av", "url": "https://sources.avar.me/data/ru-av.jsonl", "sha256": "bcd234..."}
  ],
  "package_url": "https://ios.avar.me/releases/dictionary-v43.zip",
  "package_sha256": "def456...",
  "package_size_bytes": 12345678,
  "created_at": "2026-06-19T21:30:00Z",
  "min_app_version": "1.0.0",
  "notes": "Updated entries, forms and examples."
}
```

## Поля

### `schema_version`

Версия формата `latest.json`.

Если когда-нибудь структура изменится, приложение сможет понять, поддерживает ли оно этот формат.

### `dictionary_version`

Монотонно растущая версия словаря.

Например:

```text
1, 2, 3, 4, ...
```

Приложение сравнивает свою локальную версию с этой.

### `build_id`

Уникальный идентификатор билда.

Можно использовать timestamp.

### `sources[]`

Список исходных файлов (теперь их два: `av-ru` и `ru-av`), каждый со своим `url` и `sha256`.

Помогает понять, из каких данных собран релиз.

### `package_url`

Ссылка на архив словаря.

### `package_sha256`

Хэш архива.

iOS-приложение после скачивания проверяет, что архив не повреждён.

### `package_size_bytes`

Размер архива.

Можно показывать пользователю или использовать для диагностики.

### `min_app_version`

Минимальная версия iOS-приложения, которая умеет читать этот формат словаря.

---

# 6. Содержимое архива

Файл:

```text
dictionary-v43.zip
```

Внутри:

```text
dictionary/
├── metadata.json
└── dictionary.sqlite
```

`dictionary.sqlite` содержит оба словаря (av-ru и ru-av) с таблицами записей, форм, примеров, связей и виртуальными таблицами FTS5 для поиска.

Промежуточные JSON-файлы (`dictionary.json`, `av_index.json`, `ru_index.json`) генерируются pipeline для валидации/отладки, но в релизный архив могут не включаться.

---

# 7. metadata.json

Пример:

```json
{
  "schema_version": 1,
  "dictionary_version": 43,
  "dictionaries": {
    "av-ru": {"entry_count": 22855, "index_terms": 31200},
    "ru-av": {"entry_count": 38874, "index_terms": 44800}
  },
  "entry_count_total": 61729,
  "created_at": "2026-06-19T21:30:00Z",
  "sources": [
    {"name": "av-ru", "url": "https://sources.avar.me/data/av-ru.jsonl", "sha256": "abc123..."},
    {"name": "ru-av", "url": "https://sources.avar.me/data/ru-av.jsonl", "sha256": "bcd234..."}
  ]
}
```

> Числа `entry_count` — реальные на момент изучения данных. Используются для quality gates (§15).

---

# 8. dictionary.json

Это нормализованный список словарных записей. Структура повторяет реальную схему источника (см. §3.1), а не плоский `translations`.

Пример:

```json
[
  {
    "id": "avru-000001",
    "dict": "av-ru",
    "word": "аб",
    "stress": 1,
    "stem": "а",
    "homonym": 2,
    "pos": "местоимение",
    "form": "именительный",
    "forms": ["аб", "алъ", "алъул", "ал"],
    "labels": [],
    "senses": [
      {
        "text": "это, этот, эта",
        "comment": "только",
        "labels": ["указательное местоимение"],
        "examples": [
          {"av": "аб дир къалам буго", "ru": "это мой карандаш"}
        ],
        "relations": [{"kind": "masdarfrom", "target_id": "avru-000123"}]
      }
    ],
    "see_also": [{"kind": "see", "target_id": "avru-000456", "target_word": "гьаб"}]
  }
]
```

Каждая запись помечена полем `dict` (`av-ru` / `ru-av`).

## Важно

У каждой записи должен быть стабильный `id`.

Не надо использовать порядковый номер строки как единственный ID, если порядок может меняться.

Из-за омонимов (поле `homonym`, одно слово встречается несколько раз) одного `word` недостаточно. Рекомендуемая схема:

```text
id = dict_prefix + sha1(dict + word + homonym + normalized(senses_text))
```

При коллизии хэша — добавлять числовой дизамбигуатор. Если в исходных данных появится стабильный ID — использовать его.

Поля `see_also.target` и грамматические `*from`-ссылки на этапе сборки **резолвятся в `target_id`** (с сохранением `target_word` как fallback, если цель не нашлась).

---

# 9. Поисковый индекс (аварский)

> При использовании SQLite (рекомендуется) индексы реализуются как FTS5-таблицы, а не отдельные JSON-файлы. Раздел описывает, **что** индексируется, независимо от формата.

Аварский индекс должен покрывать **оба словаря**:

- заголовки (`word`) + все `forms` из av-ru;
- аварский текст `senses[].text` из ru-av (это аварские переводы русских слов);
- опционально — `examples[].av`.

Каждый терм нормализуется (см. §11, особенно складывание палочки) и указывает на список ID записей.

Префиксный/подстрочный поиск:

- в SQLite — через FTS5 (`MATCH 'prefix*'`);
- в варианте на JSON — бинарный поиск по отсортированному массиву нормализованных ключей.

---

# 10. Поисковый индекс (русский)

Русский индекс также покрывает **оба словаря**:

- заголовки (`word`) + `forms` из ru-av;
- русский текст `senses[].text` из av-ru (русские переводы аварских слов);
- опционально — `examples[].ru`.

Нормализация русского — см. §11 (lowercase, `ё→е`, trim, NFC).

Для MVP достаточно заголовков + `senses[].text`; индексацию примеров можно включить позже.

---

# 11. Нормализация поиска

Нужно заранее договориться, как нормализовать строки.

Минимум:

- lowercase;
- trim;
- заменить `ё` на `е` для русского поиска;
- убрать лишние пробелы;
- Unicode normalization.

Для аварского важно не сломать спецсимволы. Диграфы — это обычные последовательности букв, их трогать не нужно:

```text
гӀ  къ  кӀ  лъ  хъ  гь  хь  цӀ  чӀ
```

Нельзя агрессивно удалять символы.

## 11.1. Палочка — критично для UX

Палочка `ӏ` (U+04CF, 10 692 вхождения в av-ru) на обычной клавиатуре недоступна. Пользователи набирают вместо неё разные символы. Поиск **обязан** складывать их все в одну каноническую палочку:

```text
ӏ  U+04CF  (строчная палочка, канон)
Ӏ  U+04C0  (прописная палочка)
1  цифра один
l  латинская строчная L
I  латинская/кириллическая прописная I
|  вертикальная черта
```

То есть и в индексе при сборке, и в пользовательском запросе при поиске применяется одинаковая функция нормализации. Это правило №1 по влиянию на качество аварского поиска.

## 11.2. Сводка

| Шаг | Аварский | Русский |
|---|---|---|
| lowercase | да | да |
| trim + схлопывание пробелов | да | да |
| Unicode NFC | да | да |
| складывание палочки (11.1) | **да** | — |
| `ё → е` | — | да |
| удаление диакритики/символов | **нет** | осторожно |

---

# 12. Репозиторий `avar-me/ios` (сайт + data pipeline)

Это **один** репозиторий: промо-сайт, pipeline сборки словаря и публикуемые архивы. Деплой — GitHub Pages из папки `public/` (или ветки `gh-pages`).

Рекомендуемая структура:

```text
avar-me-ios/
├── README.md
├── scripts/
│   ├── analyze_sources.py        # статистика по источникам (для гейтов)
│   ├── download_sources.py       # качает av-ru.jsonl И ru-av.jsonl
│   ├── build_dictionary.py       # строит dictionary.sqlite (+ debug JSON)
│   ├── validate_dictionary.py
│   ├── package_release.py
│   └── generate_latest.py
├── tests/
│   ├── test_build_dictionary.py
│   └── test_normalization.py     # обязательно: тесты складывания палочки
├── public/                       # ← GitHub Pages раздаёт это как ios.avar.me
│   ├── CNAME                     # ios.avar.me
│   ├── index.html                # промо-лендинг (описание, QR-код на App Store)
│   ├── assets/                   # картинки, avatar.jpg, qr.png
│   ├── latest.json
│   ├── releases/                 # dictionary-vN.zip
│   └── checksums/                # dictionary-vN.sha256
└── .github/
    └── workflows/
        └── build-and-publish.yml
```

---

# 13. Build pipeline

Pipeline запускается вручную.

Почему вручную:

- sources могут обновиться неидеально;
- сначала надо проверить другие сервисы;
- если на `dev.avar.me` всё нормально, тогда публикуем iOS-релиз.

GitHub Actions:

```yaml
name: Build and publish iOS dictionary

on:
  workflow_dispatch:
    inputs:
      dictionary_version:
        description: "Dictionary version"
        required: true
        type: string
      release_notes:
        description: "Release notes"
        required: false
        type: string

permissions:
  contents: write
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip

      - name: Download sources
        run: |
          python scripts/download_sources.py   # av-ru.jsonl + ru-av.jsonl

      - name: Build dictionary
        run: |
          python scripts/build_dictionary.py \
            --version "${{ inputs.dictionary_version }}" \
            --notes "${{ inputs.release_notes }}"

      - name: Validate dictionary
        run: |
          python scripts/validate_dictionary.py

      - name: Package release
        run: |
          python scripts/package_release.py \
            --version "${{ inputs.dictionary_version }}"

      - name: Generate latest.json
        run: |
          python scripts/generate_latest.py \
            --version "${{ inputs.dictionary_version }}" \
            --notes "${{ inputs.release_notes }}"

      - name: Commit public files
        run: |
          git config user.name "github-actions"
          git config user.email "github-actions@github.com"
          git add public/
          git commit -m "Publish dictionary v${{ inputs.dictionary_version }}" || echo "No changes"
          git push
```

Если GitHub Pages настроен на папку `public/`, сайт `https://ios.avar.me` будет отдавать эти файлы.

---

# 14. Валидация данных

Перед публикацией pipeline должен проверять:

- JSONL читается;
- нет битых JSON-строк;
- есть обязательные поля;
- нет пустых слов;
- нет пустых переводов там, где они обязательны;
- количество записей не упало неожиданно;
- индексы не пустые;
- архив успешно открывается;
- `metadata.json` совпадает с `latest.json`;
- SHA256 совпадает;
- приложение сможет понять `schema_version`.

---

# 15. Минимальные quality gates

Нужно защититься от случайного плохого релиза.

Пороги задаются **отдельно на каждый словарь** (реальные значения — см. §7). Абсолютные пороги ставим с запасом ниже текущих чисел:

```text
av-ru entry_count >= 22000   (сейчас 22855 — порог близко, важно следить)
ru-av entry_count >= 37000   (сейчас 38874)
av_index_terms    >= 20000
ru_index_terms    >= 30000
package_size_bytes >= 1000000
```

Относительное правило (сравнение с предыдущим `latest.json` / `metadata.json`), **на каждый словарь**:

```text
new_entry_count >= old_entry_count * 0.95
```

То есть падение больше 5% по любому из словарей требует ручного расследования.

**Важно:** записи без `senses` и senses без `text` — легитимны (грамматические заглушки, §3.1). Гейт «доля пустых переводов» не должен срабатывать на них; считать «битым» только то, что не парсится или теряет обязательное поле `word`.

---

# 16. Версионирование

Лучше использовать простой integer:

```text
dictionary_version = 1
dictionary_version = 2
dictionary_version = 3
```

Версия словаря не обязана совпадать с версией iOS-приложения.

Пример:

```text
iOS app version: 1.0.0
Dictionary version: 43
```

---

# 17. Откат релиза

Если опубликован плохой словарь, нужно уметь быстро откатиться.

Вариант 1:

- не удалять старые архивы;
- изменить `latest.json`, чтобы он снова указывал на старую версию.

Пример:

```json
{
  "dictionary_version": 42,
  "package_url": "https://ios.avar.me/releases/dictionary-v42.zip"
}
```

Приложение не должно автоматически откатываться на более старую версию, если у пользователя уже стоит 43.

Поэтому для emergency rollback можно добавить поле:

```json
{
  "dictionary_version": 42,
  "force_downgrade": true
}
```

Но в MVP можно обойтись без downgrade и просто выпустить v44 с исправлением.

Рекомендуемый способ:

```text
Плохой v43 → исправить → выпустить v44
```

---

# 18. iOS app: локальное хранение словаря

Приложение должно иметь два источника данных:

## 18.1. Bundled dictionary

Словарь, встроенный в приложение.

Путь:

```text
Bundle.main
```

Это fallback.

Он всегда есть.

## 18.2. Downloaded dictionary

Словарь, скачанный с `https://ios.avar.me`.

Путь:

```text
Application Support/Dictionary/current/
```

Приложение при запуске выбирает:

1. Если есть валидный скачанный словарь — использовать его.
2. Иначе использовать bundled dictionary.

---

# 19. iOS app: безопасное обновление

Нельзя заменять текущий словарь сразу во время скачивания.

Нужен atomic update.

Алгоритм:

```text
1. Скачать archive.zip во временную папку.
2. Проверить SHA256.
3. Распаковать во временную папку.
4. Прочитать metadata.json.
5. Проверить schema_version.
6. Проверить dictionary_version.
7. Проверить, что dictionary.sqlite открывается и FTS-таблицы читаются (например пробный SELECT).
8. Переместить текущий словарь в previous/.
9. Переместить новый словарь в current/.
10. Записать current version в UserDefaults.
```

Если что-то пошло не так:

```text
оставить старый словарь
```

Пользователь не должен получить сломанное приложение.

---

# 20. iOS app: проверка обновлений

Приложение раз в сутки проверяет:

```text
https://ios.avar.me/latest.json
```

Алгоритм:

```text
1. Прочитать локальную dictionary_version.
2. Скачать latest.json.
3. Если latest.dictionary_version <= local.dictionary_version — ничего не делать.
4. Если latest.min_app_version > current_app_version — ничего не делать.
5. Скачать package_url.
6. Проверить package_sha256.
7. Установить новый словарь.
```

---

# 21. Ночное обновление

iOS не гарантирует точный запуск ночью.

Нельзя рассчитывать, что приложение всегда проснётся в 03:00.

Правильный подход:

## 21.1. При запуске приложения

Если последняя проверка была больше 24 часов назад:

```text
check for updates
```

## 21.2. Background App Refresh

Добавить фоновую задачу:

```text
BGAppRefreshTask
```

Она может периодически проверять обновления.

Важно:

- iOS сама решает, когда запускать background refresh;
- пользователь может отключить Background App Refresh;
- нельзя гарантировать точное ночное время;
- поэтому основной надёжный механизм — проверка при открытии приложения.

---

# 22. UX обновления

Не надо мешать пользователю.

Хороший UX:

```text
Словарь обновлён до версии 43
```

Можно показывать ненавязчиво в настройках или маленьким toast.

На экране настроек:

```text
Версия словаря: 43
Последняя проверка: 2026-06-19 23:10
Проверить обновления
```

Кнопка:

```text
Проверить обновления
```

---

# 23. App Store review considerations

Приложение скачивает только словарные данные.

Это не исполняемый код.

Нельзя скачивать и исполнять внешний код.

Словарные данные должны быть контентом:

```text
JSON / SQLite / ZIP
```

---

# 24. iOS project structure

Отдельный репозиторий **`../avarme-ios`**.

```text
AvarDictionary/
├── App/
│   └── AvarDictionaryApp.swift
├── Models/
│   ├── DictionaryEntry.swift
│   ├── DictionaryMetadata.swift
│   └── DictionaryManifest.swift
├── Services/
│   ├── DictionaryStore.swift
│   ├── DictionaryLoader.swift
│   ├── DictionarySearchService.swift
│   ├── DictionaryUpdateService.swift
│   └── ChecksumService.swift
├── ViewModels/
│   ├── SearchViewModel.swift
│   ├── EntryDetailViewModel.swift
│   └── SettingsViewModel.swift
├── Views/
│   ├── SearchView.swift
│   ├── EntryDetailView.swift
│   ├── SettingsView.swift
│   └── Components/
├── Resources/
│   └── BundledDictionary/
│       ├── metadata.json
│       └── dictionary.sqlite      # bundled fallback (оба словаря, FTS5)
└── Utilities/
    ├── TextNormalizer.swift        # включая складывание палочки (§11.1)
    └── FileManagerExtensions.swift
```

`DictionaryStore` / `DictionaryLoader` работают с SQLite (FTS5) через прямой C-API `sqlite3` или `GRDB`-подобную обёртку (для MVP — без сторонних зависимостей, голый `sqlite3`).

---

# 25. Основные Swift-сервисы

## 25.1. DictionaryStore

Отвечает за текущий активный словарь.

Функции:

```swift
loadActiveDictionary()
getEntry(id:)
search(query: direction:)
```

## 25.2. DictionaryUpdateService

Отвечает за обновления.

Функции:

```swift
checkForUpdates()
downloadPackage()
verifyPackage()
installPackage()
```

## 25.3. ChecksumService

Функции:

```swift
sha256(fileURL:)
```

## 25.4. TextNormalizer

Функции:

```swift
normalizeAvar(_ text: String) -> String
normalizeRussian(_ text: String) -> String
```

---

# 26. Поиск

В MVP:

- открываем `dictionary.sqlite`;
- запрос нормализуем (для аварского — складывание палочки, §11.1);
- ищем через FTS5: точное совпадение, затем префикс (`MATCH 'term*'`);
- направление выбирает, в каком словаре/индексе искать.

Направления:

```swift
enum SearchDirection {
    case avarToRussian   // ищем по аварскому индексу
    case russianToAvar   // ищем по русскому индексу
}
```

---

# 27. Избранное и история

Хранить не слова, а ID записей.

```text
favorites = ["avru-000001", "avru-000245"]
history = ["сагьвил", "магӀна"]
```

Почему ID:

- слово может измениться;
- перевод может измениться;
- запись может обновиться.

---

# 28. Что делать, если ID исчез после обновления

Если избранная запись исчезла:

- не падать;
- скрыть её из списка;
- можно показать в настройках: "Некоторые избранные слова больше не доступны".

---

# 29. Security

Минимум:

- только HTTPS;
- SHA256 проверка архива;
- не исполнять никакой код;
- не открывать произвольные URL из `latest.json`, если не нужно.

Можно ограничить домен:

```text
package_url must start with https://ios.avar.me/
```

---

# 30. Первые задачи для Claude

## Задача 1

Создай репозиторий build pipeline для iOS словаря.

Нужно:

- Python 3.12
- скрипт скачивания **обоих** источников: `av-ru.jsonl` и `ru-av.jsonl`
- скрипт нормализации данных (с правильным складыванием палочки, §11.1)
- сборка `dictionary.sqlite` (оба словаря + FTS5) и `metadata.json`
- (для отладки) генерация `dictionary.json` / индексов в JSON
- упаковка в `dictionary-vN.zip`
- генерация `latest.json` (с массивом `sources[]`)
- SHA256 для архива
- per-dictionary quality gates с реальными порогами (§15)
- GitHub Actions workflow для ручного запуска, деплой на GitHub Pages

## Задача 2

Создай SwiftUI iOS приложение.

Нужно:

- SwiftUI
- iOS 18+
- MVVM
- bundled dictionary
- загрузка словаря из Bundle
- поиск по аварскому
- карточка слова
- переключатель av→ru / ru→av

## Задача 3

Добавь обновление словаря.

Нужно:

- проверка `https://ios.avar.me/latest.json`
- сравнение версий
- скачивание ZIP
- SHA256 validation
- atomic install в Application Support
- fallback на bundled dictionary
- экран настроек с версией словаря

---

# 31. Первый prompt для Claude: data pipeline

```text
We need to build a GitHub Pages data pipeline for an iOS dictionary app.
Repo: github.com/avar-me/ios (site + pipeline + published archives).

Source data (TWO independent dictionaries):
- https://sources.avar.me/data/av-ru.jsonl  (Avar→Russian, ~22855 entries)
- https://sources.avar.me/data/ru-av.jsonl  (Russian→Avar, ~38874 entries)

Real source schema (NOT a flat "translations" field):
word, stress, stem, homonym, forms[], pos, form, gender_forms,
senses[] each with: text, comment, precomment, labels[],
examples[] (av, ru, labels, comment), and grammar relations
(masdarfrom, genitivefrom, pluralfor, forceto, participlefrom, ...),
plus see_also[] {target, kind: see|from}.
Note: some entries have empty senses or senses without text — these are
legitimate grammatical stub-forms, do NOT discard them.

Target domain: https://ios.avar.me (GitHub Pages, DNS via Cloudflare).

The pipeline should be manually triggered via GitHub Actions workflow_dispatch.

Requirements:
1. Download BOTH source JSONL files.
2. Validate source records (only "word" is strictly required).
3. Normalize, preserving the rich schema. Avar normalization MUST fold
   palochka variants (ӏ U+04CF, Ӏ U+04C0, 1, l, I, |) to canonical ӏ.
   Russian normalization: lowercase, ё→е, trim, NFC.
4. Assign stable IDs (account for homonyms) and resolve see_also/*from
   targets to IDs.
5. Build dictionary.sqlite containing BOTH dictionaries with FTS5 search
   indexes (Avar index and Russian index, each covering both dicts).
   Also emit metadata.json. (JSON dumps for debugging are optional.)
6. Package into releases/dictionary-v{version}.zip + checksums/*.sha256.
7. Generate latest.json (with sources[] array of {name,url,sha256}).
8. Commit generated files into public/ for GitHub Pages.
9. Add PER-DICTIONARY quality gates (real thresholds):
   av-ru entry_count >= 22000, ru-av entry_count >= 37000,
   indexes not empty, >5% drop vs previous = fail, package readable,
   SHA256 matches.
10. Use Python 3.12. Avoid external dependencies (sqlite3 is stdlib).

Please generate:
- repository structure
- Python scripts
- GitHub Actions workflow
- README with usage instructions
```

---

# 32. Первый prompt для Claude: iOS app

```text
Create a SwiftUI iOS dictionary app for Avar↔Russian search.
Separate repo: avarme-ios.

Requirements:
- SwiftUI, iOS 18+, MVVM, no third-party dependencies for MVP
- bundled offline dictionary as SQLite + FTS5:
  - Resources/BundledDictionary/dictionary.sqlite
  - Resources/BundledDictionary/metadata.json
  - read via stdlib sqlite3 C-API
- the SQLite holds TWO dictionaries (av-ru and ru-av), each entry tagged
  with its dict; rich schema: word, stress, stem, homonym, forms, pos,
  form, senses[] (text, comment, labels, examples[av,ru]), see_also
  (resolved to target ids).
- search directions: Avar → Russian, Russian → Avar (pick the dictionary)
- Avar input normalization MUST fold palochka variants (ӏ Ӏ 1 l I |) → ӏ
- search screen, word detail screen (render senses, examples, see_also
  links), settings screen
- show dictionary version
- support Russian and Avar Cyrillic text
- dark mode + Dynamic Type support

Please generate:
- Xcode project structure
- Swift models
- dictionary loading service
- search service
- SwiftUI views
- instructions for running in Xcode
```

---

# 33. Prompt для Claude: iOS updates

```text
Add dictionary data updates to the SwiftUI iOS app.

Update endpoint:
https://ios.avar.me/latest.json

latest.json contains:
- schema_version
- dictionary_version
- build_id
- sources[] (array of {name, url, sha256})
- package_url
- package_sha256
- package_size_bytes
- created_at
- min_app_version
- notes

Requirements:
1. The app ships with a bundled dictionary.
2. The app can download a newer dictionary package from package_url.
3. The app verifies SHA256 before installing.
4. The app installs updates atomically:
   - download to temp
   - verify
   - unzip to temp
   - validate metadata
   - move to Application Support/Dictionary/current
5. If update fails, continue using previous dictionary.
6. Check for updates when app launches if last check was more than 24 hours ago.
7. Add a Settings screen:
   - current dictionary version
   - last update check
   - manual "Check for updates" button
8. Add Background App Refresh using BGAppRefreshTask, but do not rely on exact nightly timing.

Please implement this cleanly with MVVM and async/await.
```

---

# 34. Roadmap

## Phase 1

- build pipeline
- GitHub Pages publication
- latest.json
- downloadable ZIP

## Phase 2

- iOS app with bundled dictionary
- search
- detail screen

## Phase 3

- iOS app remote dictionary updates
- manual update button
- daily check

## Phase 4

- background refresh
- favorites
- history

## Phase 5

- App Store release

---

# 35. Final recommendation

Start with the data pipeline first.

Reason:

- it defines the stable contract for the app;
- Claude can build and test it quickly;
- once `https://ios.avar.me/latest.json` and ZIP archives exist, the iOS app has a real backend to integrate with.

Recommended first milestone:

```text
Open https://ios.avar.me/latest.json in browser
Download dictionary-v1.zip
Unzip it
See metadata.json, dictionary.json, av_index.json, ru_index.json
```

After that, start the SwiftUI app.
