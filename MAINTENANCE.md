# MAINTENANCE — публикация и обслуживание словаря

Runbook для репозитория `avar-me/ios` (data-pipeline + сайт `ios.avar.me`).
Общая архитектура — в [`PLAN.md`](PLAN.md). Схема исходных данных — в
[`docs/source-schema.md`](docs/source-schema.md).

## Опубликовать новую версию словаря

Данные обновляются **без обновления приложения** — пользователи получают
новый словарь автоматически (проверка `latest.json` при запуске / по кнопке).

### Локально

```bash
cd avar/ios
python3 scripts/download_sources.py                       # av-ru.jsonl + ru-av.jsonl
python3 scripts/analyze_sources.py                        # сверить объёмы (для гейтов)
python3 scripts/build_dictionary.py --version N --notes "…"
python3 scripts/validate_dictionary.py                    # quality gates
python3 scripts/package_release.py --version N            # ZIP + SHA-256
python3 scripts/generate_latest.py --version N --notes "…"
git add public/ && git commit -m "Publish dictionary vN" && git push
```

`N` — монотонно растущее целое (текущее значение см. в `public/latest.json`).
Push в `public/**` автоматически триггерит деплой GitHub Pages.

### Через GitHub Actions

Actions → **Build and publish iOS dictionary** → **Run workflow**.
- `dictionary_version` — **оставь пустым**: версия сама возьмётся из `latest.json` и +1.
  (Можно задать вручную, если нужен конкретный номер.)
- `release_notes` — по желанию.

Прогонит тесты → весь пайплайн → коммит в `public/` → **и сам задеплоит на Pages**
(деплой встроен в этот workflow, т.к. push от `GITHUB_TOKEN` не триггерит отдельный
`deploy-pages.yml`; push устойчив к гонкам — rebase + повтор).

> Если когда-то увидишь, что релиз закоммичен, но `ios.avar.me` отдаёт старую
> версию — запусти деплой вручную: `gh workflow run deploy-pages.yml`.

## Деплой сайта

GitHub Pages в режиме **build_type = workflow** (НЕ «deploy from branch» —
он разрешает только `/` или `/docs`, а сайт лежит в `public/`).
Публикует `.github/workflows/deploy-pages.yml` (upload-pages-artifact из `public/`).

- Автоматически: при push в `public/**`.
- Вручную **без коммита**: `gh workflow run deploy-pages.yml` (или Actions → Run).

DNS `avar.me` — на Cloudflare; `ios.avar.me` через CNAME на Pages.
Примечание: Cloudflare включает Email Obfuscation — `mailto:` на страницах
(например privacy) шифруется в `/cdn-cgi/l/email-protection`; для пользователей
декодируется обратно, это не ошибка.

## Откат релиза

Старые архивы в `public/releases/` не удаляются.
- Лёгкий путь: исправить и выпустить `vN+1` (рекомендуется).
- Быстрый откат: перегенерировать `latest.json` на предыдущую версию
  (приложение не откатывается на версию ниже установленной у пользователя —
  для emergency downgrade пришлось бы добавить флаг; в проде не использовалось).

## Quality gates (см. `scripts/config.py`)

Пороги на каждый словарь (реальные числа на 2026-06):
- av-ru: ≥ 22 000 записей · ru-av: ≥ 37 000 записей
- падение > 5 % к предыдущему релизу → сборка падает (ручное расследование)
- архив ≥ 1 MB, индексы непустые, SHA-256 совпадает, `metadata` валиден

## Структура релиза

```
public/
├── latest.json                 # манифест: версия, sources[], package_url, sha256
├── releases/dictionary-vN.zip  # внутри: dictionary/{metadata.json, dictionary.sqlite}
└── checksums/dictionary-vN.sha256
```

`dictionary.sqlite`: таблицы `entries(id,dict,word,homonym,pos,data)`,
`search(lang,term,entry_id,weight)` (FTS-подобный индекс, поиск exact+prefix),
`meta(key,value)`. Нормализация (палочка) — `scripts/normalize.py`, она же
зеркалится в приложении (`TextNormalizer.swift`).
