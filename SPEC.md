# SPEC.md — «Передчуття» (Foresight Cart)

> **Для AI-агента-розробника (Claude Code / VS Code).**
> Це повна специфікація MVP. Реалізуй її повністю, у порядку з §12.
> Мова коду, ідентифікаторів, коментарів, комітів — **англійська**. Мова UI-текстів — **українська**.
> Не вигадуй нових фіч поза цим документом. Якщо щось неоднозначне — обери простіше рішення і залиш `# SPEC-GAP:` коментар.

---

## 1. Що будуємо

Автономний агент, що працює «під капотом» кошика Сільпо. При зміні кошика він сам збирає контекст через офіційний MCP «Сільпо», рахує погодний шок через Open-Meteo, будує hazard-модель циклу споживання на чеках Гостя і пропонує **0–3 товари**, які Гість забув, з обґрунтуванням із його ж історії.

**Продуктовий інваріант, який не можна порушити:** агент має право повернути **порожній результат**. Нуль рекомендацій — валідний і бажаний вихід, коли впевненість низька. Ніколи не заповнюй слоти «щоб було».

**Демо-цінність:** журі має бачити живий JSON-RPC трейс викликів MCP у UI.

---

## 2. Стек

| Шар | Технологія | Версія |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS + Zustand | Vite 5 |
| Backend | FastAPI + Uvicorn, Python | 3.12 |
| MCP | `mcp` (офіційний Python SDK), `streamablehttp_client` | latest |
| LLM | Anthropic SDK, `claude-sonnet-4-6` | — |
| Weather | Open-Meteo Forecast API + Archive API (без ключа) | v1 |
| Store | PostgreSQL 16 + SQLAlchemy 2 (async) + Alembic | — |
| Cache/Queue | Redis 7 + `arq` | — |
| Math | NumPy, SciPy, Pandas | — |
| Infra | Docker Compose | — |

---

## 3. Структура репозиторію

```
foresight/
├── docker-compose.yml
├── .env.example
├── README.md
├── Makefile
├── api/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py                 # FastAPI app, CORS, routers, lifespan
│       ├── config.py               # pydantic-settings
│       ├── db.py                   # async engine, session
│       ├── models/
│       │   ├── orm.py              # SQLAlchemy tables
│       │   └── schemas.py          # Pydantic DTO (див. §8)
│       ├── auth/
│       │   ├── oauth.py            # OAuth 2.1 + PKCE + DCR
│       │   └── token_store.py      # Fernet-encrypted tokens in Postgres
│       ├── mcp/
│       │   ├── client.py           # session pool, call_tool wrapper, retry
│       │   ├── tools.py            # typed facades over silpo_* tools
│       │   └── trace.py            # JSON-RPC trace recorder
│       ├── weather/
│       │   ├── openmeteo.py        # forecast + archive fetchers
│       │   └── delta.py            # WeatherDelta engine (§6)
│       ├── engine/
│       │   ├── hazard.py           # replenishment model (§7.1)
│       │   ├── elasticity.py       # weather elasticity (§7.2)
│       │   ├── scoring.py          # final score (§7.3)
│       │   ├── guardrails.py       # hard filters (§7.4)
│       │   ├── reasoner.py         # Claude structured output (§7.5)
│       │   └── orchestrator.py     # 7 phases, SSE emitter (§5)
│       ├── routers/
│       │   ├── auth.py
│       │   ├── agent.py            # /agent/run (SSE), /agent/apply
│       │   ├── trace.py
│       │   └── health.py
│       ├── fixtures/
│       │   ├── weather_storm.json
│       │   ├── weather_heat.json
│       │   ├── weather_frost.json
│       │   └── demo_history.json   # fallback, якщо MCP-акаунт порожній
│       └── worker.py               # arq: T-90min job, feature refresh, T+72h eval
└── web/
    ├── Dockerfile
    ├── vite.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── store.ts                # Zustand
        ├── api.ts                  # fetch + EventSource
        ├── components/
        │   ├── CartPanel.tsx
        │   ├── ForesightPanel.tsx  # 0–3 картки + Undo
        │   ├── SuggestionCard.tsx
        │   ├── WeatherBadge.tsx
        │   ├── SlotConflictCard.tsx
        │   ├── AgentTrace.tsx      # SSE-стрічка фаз
        │   ├── McpInspector.tsx    # RAW JSON-RPC
        │   └── DemoControls.tsx    # перемикач погодних сценаріїв
        └── styles/tokens.css
```

---

## 4. Конфігурація

`.env.example`:

```env
# MCP
SILPO_MCP_URL=https://mcp.silpo.ua/mcp
OAUTH_REDIRECT_URI=http://localhost:8000/auth/silpo/callback
OAUTH_CLIENT_NAME=foresight-hackathon-agent

# LLM
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6

# Weather
OPEN_METEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast
OPEN_METEO_ARCHIVE_URL=https://archive-api.open-meteo.com/v1/archive

# Infra
DATABASE_URL=postgresql+asyncpg://foresight:foresight@postgres:5432/foresight
REDIS_URL=redis://redis:6379/0
TOKEN_ENCRYPTION_KEY=            # Fernet.generate_key()
CORS_ORIGINS=http://localhost:5173

# Engine thresholds (tunable, НЕ хардкодити в коді)
MIN_CONFIDENCE=0.62
MAX_SUGGESTIONS=3
PRICE_CAP_RATIO=0.12
MIN_PURCHASES_FOR_CYCLE=3
SHRINKAGE_K=8
SHOCK_DELTA_APPARENT=7.0
SHOCK_Z_SCORE=1.8
DEBOUNCE_SECONDS=20
DISMISS_BAN_DAYS=90

# Demo
DEMO_MODE=true                   # вмикає фікстури погоди + DemoControls
```

**Безпека (вимога хакатону):** MCP-токен і Silpo JWT ніколи не потрапляють у фронтенд. Frontend оперує лише `session_id` у httpOnly cookie. Токени лежать у Postgres, зашифровані Fernet.

---

## 5. Оркестрація: 7 фаз

`engine/orchestrator.py` — єдина точка входу. Кожна фаза емітить SSE-подію (див. §8.3).

```python
async def run_agent(session_id: str, trigger: Trigger) -> AgentResult:
    # PHASE 0 — BOOTSTRAP
    #   tools/list  (кешувати 1h; НЕ хардкодити схеми аргументів)
    #   silpo_get_my_shopping_cart      -> cart_id | exists=False
    #   if not exists: НЕ створювати кошик автоматично; повернути NO_CART
    #   silpo_get_shopping_cart_by_id   -> items, branchId, deliveryType, timeslot,
    #                                      validations, loyalty, checkoutWebLink
    #   cart_ctx = {branchId, deliveryType, timeslot}   # ключ до всіх 🔒 tools

    # PHASE 1 — CONTEXT FAN-OUT (asyncio.gather, ліміт 6 одночасних, бюджет 3s)
    #   A profile : silpo_get_my_profile, silpo_get_my_family,
    #               silpo_get_my_food_restrictions, silpo_get_my_favorites,
    #               silpo_get_my_delivery_addresses
    #   B history : silpo_get_my_offline_orders, silpo_get_my_online_orders  (12 міс)
    #   C commerce: silpo_get_promotions(cart_ctx), silpo_get_my_promos,
    #               silpo_get_my_coupons, silpo_get_loyalty_info
    #   D weather : forecast(lat,lng) + climate_normals(lat,lng)
    #   Будь-який збій гілки != фатальний: degrade gracefully, лог у trace.

    # PHASE 2 — WEATHER DELTA  (детерміновано, БЕЗ LLM)
    #   delta = compute_weather_delta(forecast, normals, timeslot)
    #   if not delta.shock: продовжуємо ТІЛЬКИ replenishment-гілкою

    # PHASE 3 — REPLENISHMENT HAZARD
    #   candidates = hazard.score_all(history, cart_items)

    # PHASE 4 — WEATHER ELASTICITY
    #   candidates = elasticity.apply(candidates, delta, history, archive)
    #   candidates = scoring.finalize(candidates, promos)

    # PHASE 5 — GUARDRAILS
    #   candidates = guardrails.filter(candidates, restrictions, cart, budget)
    #   slot_action = check_slot_conflict(delta, timeslot)   # окрема гілка

    # PHASE 6 — REASONING
    #   suggestions = await reasoner.explain(candidates[:MAX_SUGGESTIONS], facts)
    #   ЗАПИСУ В КОШИК ТУТ НЕМАЄ. Тільки після POST /agent/apply.

    # PHASE 7 — фоново (worker.py), не в цьому виклику
```

**Тригери** (`Trigger` enum): `CART_UPDATED` (debounce 20s), `CHECKOUT_INTENT`, `PRE_SLOT_T90` (cron), `WEATHER_CHANGED`.

---

## 6. Погодний модуль

### 6.1 Forecast
```
GET {OPEN_METEO_FORECAST_URL}
  ?latitude={lat}&longitude={lng}
  &hourly=temperature_2m,apparent_temperature,precipitation,
          precipitation_probability,wind_gusts_10m,weather_code,relative_humidity_2m
  &forecast_days=3&timezone=auto
```

### 6.2 Climate normals (Archive)
```
GET {OPEN_METEO_ARCHIVE_URL}
  ?latitude={lat}&longitude={lng}
  &start_date={today-10y}&end_date={today-1d}
  &daily=temperature_2m_mean,apparent_temperature_mean,precipitation_sum,wind_gusts_10m_max
  &timezone=auto
```
Нормаль рахуємо як `μ, σ` по вікну ±7 календарних днів навколо сьогоднішньої дати за 10 років. Кешуємо в Postgres таблиці `climate_normals(lat_bucket, lng_bucket, doy, mu, sigma)` — перерахунок раз на добу, бакетизація координат до 0.1°.

### 6.3 `WeatherDelta`
```python
@dataclass
class WeatherDelta:
    delta_apparent: float      # mean(apparent[0..24h]) - mean(apparent[-7d..0])
    z_score: float             # (t_today - mu) / sigma
    first_frost: bool          # перший перехід t_min < 0 цього сезону
    first_heat: bool           # перший t_max > 28 цього сезону
    storm_in_slot: bool        # precip > 8mm ЛИБО gusts > 15 m/s у вікні слоту
    rain_next_24h_mm: float
    grey_streak_days: int      # днів поспіль із weather_code in {3,45,48,51,53,61,63}
    shock: bool                # |delta_apparent|>=7 OR |z|>=1.8 OR storm_in_slot
    shock_strength: float      # 0..1, нормалізована: max(|delta|/12, |z|/3, storm*1.0)
    summary_uk: str            # коротко для UI: «злива 14 мм о 19:00, пориви 19 м/с»
```

### 6.4 Демо-режим
При `DEMO_MODE=true` фронтенд може передати `?weather_fixture=storm|heat|frost|none`.
Бекенд читає `fixtures/weather_*.json` замість реального API. **Усі MCP-виклики при цьому залишаються реальними** — фікстурується тільки погода, щоб демо не залежало від реальної хмарності.

---

## 7. Алгоритми

### 7.1 Hazard / цикл споживання (`engine/hazard.py`)

Вхід: об'єднана історія `silpo_get_my_offline_orders` + `silpo_get_my_online_orders` за 12 міс.

```
Для кожного product_key (нормалізований SKU → категорія+бренд+обсяг):
  purchases = відсортовані дати покупок
  if len(purchases) < MIN_PURCHASES_FOR_CYCLE: -> only_weather_branch = True, skip hazard
  ipi = [d(i+1) - d(i)]                       # міжпокупкові інтервали, дні
  median_ipi = median(ipi)
  mad = median(|ipi - median_ipi|)
  shape k = clamp(1.2 + median_ipi / max(mad, 1), 1.2, 5.0)   # Weibull shape
  scale λ = median_ipi / (ln 2)**(1/k)
  t = days_since_last_purchase
  p_out = 1 - exp(-((t/λ)**k))                # CDF Weibull = P(запас вичерпано)
  # корекція на горизонт доставки
  t_next = t + days_until_next_realistic_delivery   # за замовчуванням 4
  p_out_horizon = 1 - exp(-((t_next/λ)**k))
```
Повертає `Candidate(product_key, p_out, median_ipi, days_since_last, last_purchase_date, source='hazard')`.

**Нормалізація SKU:** зводимо варіації одного товару в один `product_key` (напр. «Кава Lavazza 1 кг» і «Кава Lavazza 500 г» → `coffee_beans:lavazza`). Мапінг: категорія з MCP + нормалізований бренд. Зберігати в `sku_map` таблиці; для MVP — простий словник + fuzzy по назві (rapidfuzz, поріг 85).

### 7.2 Погодна еластичність (`engine/elasticity.py`)

```
Для кожної категорії c:
  Побудувати denormalized dataset: за кожен день останніх 12 міс
    y = 1, якщо в цей день був чек із категорією c, інакше 0
    x = [delta_apparent(day), z_score(day), precip(day), first_frost(day), ...]
       ← беремо з Archive API за датою чека
  β_guest = логістична регресія (sklearn/scipy, L2, C=1.0)
  n_obs = кількість покупок категорії c у Гостя
  w = n_obs / (n_obs + SHRINKAGE_K)
  β_final = w * β_guest + (1 - w) * β_segment
```
`β_segment` для MVP — константна таблиця пріорів у `elasticity_priors.yaml` (категорія × погодна фіча), заповнена експертно: напр. `hot_drinks: {delta_apparent: -0.35, first_frost: +0.8}`, `bottled_water: {z_score: +0.55, first_heat: +1.1}`, `pet_food: {storm_in_slot: +0.25}`.

### 7.3 Фінальний скор (`engine/scoring.py`)

```
logit_p = a * logit(p_out_horizon)
        + b * (β_final · weather_features) * shock_strength
        + c * promo_lift
        + d * favorite_flag
p_final = sigmoid(logit_p)

a = 1.0, b = 0.6, c = 0.25, d = 0.15     # у config, не в коді
promo_lift = 1, якщо товар у silpo_get_my_promos/get_promotions, інакше 0
favorite_flag = 1, якщо товар у silpo_get_my_favorites
```
Кожен кандидат несе `evidence: list[Evidence]` — факти, з яких зібрано скор. **Кандидат без жодного evidence автоматично відкидається.**

### 7.4 Guardrails (`engine/guardrails.py`) — жорсткі, у цьому порядку

1. `in_cart` — товар або його аналог уже в кошику → drop.
2. `dietary` — конфлікт із `silpo_get_my_food_restrictions`. Перевірка **за складом** через `silpo_get_product_details`, не за назвою.
3. `restricted_category` — алкоголь, тютюн, дитяче харчування до 6 міс → ніколи в автопропозицію.
4. `availability` — товар відсутній → `silpo_get_replacements` → якщо заміни немає, drop.
5. `budget` — сума пропозицій > `PRICE_CAP_RATIO` × сума кошика → обрізати знизу по скору.
6. `confidence` — `p_final < MIN_CONFIDENCE` → drop.
7. `grounded` — немає evidence → drop.
8. `dismissed_ban` — `product_key` відхилений Гостем ≥2 рази за `DISMISS_BAN_DAYS` → drop.
9. `cap` — зрізати до `MAX_SUGGESTIONS`.

Кожен drop пишеться в trace з причиною — це видно в UI і це окремий аргумент на пітчі.

### 7.5 Reasoner (`engine/reasoner.py`)

LLM **не обирає товари**. Він отримує вже відфільтрованих кандидатів із фактами і формулює причину.

System prompt (англійською, вивести в `prompts/reasoner.md`):
```
You are the explanation layer of a grocery replenishment agent.
You receive pre-selected, pre-validated candidates with hard evidence.
You DO NOT add, remove, or reorder candidates. You DO NOT invent facts.
For each candidate write one reason in Ukrainian, max 90 characters,
referencing at least one concrete evidence item (a date, a day count, or a weather figure).
Tone: calm, factual, no sales language, no exclamation marks, no emoji.
Return strict JSON matching the provided schema. No prose outside JSON.
```
Використовуй structured output / tool-use зі схемою:
```json
{"suggestions":[{"product_key":"str","reason_uk":"str","evidence_used":["str"]}]}
```
Валідація відповіді: якщо `product_key` не з вхідного списку → відкинути. Якщо `evidence_used` порожній → fallback на шаблонну причину, згенеровану детерміновано з `Evidence`.

### 7.6 Конфлікт погоди зі слотом

Окрема, незалежна від товарів гілка:
```
if delta.storm_in_slot:
    slots = silpo_get_time_slots(branchId, deliveryType)
    безпечні = слоти без storm за прогнозом, у межах ±6 год
    → SlotAction(current, proposed, reason_uk)
    → застосовується тільки через POST /agent/apply {action: "shift_slot"}
       → silpo_update_shopping_cart(timeslot=...)
```

---

## 8. Контракти API

### 8.1 Pydantic-моделі (`models/schemas.py`)
```python
class Evidence(BaseModel):
    kind: Literal["cycle","history_date","weather","family","promo","favorite","absence"]
    text_uk: str
    value: float | str | None = None

class Suggestion(BaseModel):
    product_key: str
    product_id: str | None
    name: str
    price: float | None
    image_url: str | None
    reason_uk: str
    confidence: float
    evidence: list[Evidence]

class SlotAction(BaseModel):
    current_start: datetime
    current_end: datetime
    proposed_start: datetime
    proposed_end: datetime
    reason_uk: str

class AgentResult(BaseModel):
    run_id: str
    status: Literal["ok","no_cart","silent","error"]
    suggestions: list[Suggestion]          # може бути []
    slot_action: SlotAction | None
    weather: WeatherDelta
    silent_reason: str | None              # чому нічого не запропоновано
    trace_url: str
```

### 8.2 Endpoints
| Метод | Шлях | Опис |
|---|---|---|
| `GET` | `/auth/silpo/login` | старт OAuth 2.1 + PKCE, редірект на `/authorize` |
| `GET` | `/auth/silpo/callback` | обмін коду на токен, httpOnly cookie `fs_session` |
| `GET` | `/auth/status` | `{authorized: bool, guest_name: str}` |
| `GET` | `/agent/run` | **SSE**. Query: `trigger`, `weather_fixture?` |
| `POST` | `/agent/apply` | `{run_id, action: "add_products"\|"shift_slot", product_keys[]}` |
| `POST` | `/agent/feedback` | `{run_id, product_key, action: "accept"\|"dismiss", reason?}` |
| `GET` | `/cart` | поточний кошик (проксі до MCP, для UI) |
| `GET` | `/trace/{run_id}` | повний JSON-RPC трейс, `?format=json\|ndjson` |
| `GET` | `/health` | liveness |

### 8.3 SSE-події `/agent/run`
```
event: phase   data: {"phase":0,"name":"bootstrap","status":"start"}
event: tool    data: {"tool":"silpo_get_my_offline_orders","ms":412,"ok":true,
                      "request":{...},"response_preview":{...}}
event: think   data: {"text":"Кава: 21 день від останньої покупки, цикл 19 днів"}
event: drop    data: {"product_key":"kefir","rule":"dietary","detail":"лактоза"}
event: result  data: <AgentResult>
event: error   data: {"phase":1,"message":"..."}
```
`AgentTrace.tsx` рендерить `phase`/`think`/`drop`, `McpInspector.tsx` рендерить `tool` з RAW JSON.

---

## 9. MCP-клієнт

`mcp/client.py`:
```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(settings.SILPO_MCP_URL, auth=provider) as (r, w, _):
    async with ClientSession(r, w) as s:
        await s.initialize()
        tools = await s.list_tools()          # кеш 1h, логувати в trace
```

**Правила:**
- **НЕ хардкодити схеми аргументів tools.** Читати `tools/list` на старті, валідувати виклики проти отриманої JSON Schema, при розбіжності — лог `SPEC-GAP` і degrade.
- Обгортка `call_tool(name, args)` робить: trace-запис (request/response/латентність), retry з експоненційним backoff на `429` (0.5s → 1s → 2s → 4s, max 4 спроби), `401` → refresh token → повтор один раз, `403`/`-32601` → фатально для цієї гілки, не для всього ранy.
- Усі 🔒 cart tools отримують `branchId`, `deliveryType`, `timeslot` з `cart_ctx`, зібраного у Фазі 0.
- Порядок обов'язковий: `silpo_get_my_shopping_cart` → `silpo_get_shopping_cart_by_id` → (для write-сценаріїв) `silpo_get_time_slots` для валідації слоту.
- Після кожного write — верифікація через `silpo_get_shopping_cart_by_id`, перевірка `validations[]`.
- Якщо `loyalty.bonusAvailable > 0` і `loyalty.bonusRequested is None` і `loyalty.isEnabled` → показати в UI пропозицію балабонусів (застосовувати лише за кліком).

**Tools, які використовує MVP (мінімум 14):**
`silpo_get_my_shopping_cart`, `silpo_get_shopping_cart_by_id`, `silpo_get_time_slots`, `silpo_get_my_profile`, `silpo_get_my_family`, `silpo_get_my_food_restrictions`, `silpo_get_my_favorites`, `silpo_get_my_offline_orders`, `silpo_get_my_online_orders`, `silpo_get_promotions`, `silpo_get_my_promos`, `silpo_get_loyalty_info`, `silpo_find_products_batch`, `silpo_get_product_details`, `silpo_get_replacements`, `silpo_add_or_update_cart_products`, `silpo_update_shopping_cart`.

---

## 10. Frontend

### 10.1 Дизайн-токени (`styles/tokens.css`)
```css
:root{
  --ink:#101418;        /* трейс-панель, темні поверхні */
  --paper:#FFFFFF;
  --haze:#EEF1F4;       /* нейтральна поверхня карток */
  --silpo:#E4002B;      /* ТІЛЬКИ дія агента: кнопка «Додати», бейдж впевненості */
  --storm:#2E4A6B;      /* погодний сигнал */
  --muted:#5A6472;
  --ok:#1B7F5A;
  --radius-card:14px;
  --radius-pill:999px;
}
```
Шрифти: **Manrope** (400/600/800) для інтерфейсу, **JetBrains Mono** 12px тільки для `McpInspector`. Обидва з Google Fonts, підключити `&subset=cyrillic`.

**Правила, яких дотримуватись:**
- Червоний `--silpo` з'являється максимум у двох місцях на екрані. Уся решта — нейтральна.
- Жодних ALL-CAPS лейблів, жодних акцентних смужок під заголовками, жодних градієнтних заливок.
- Нумерація `01/02/…` дозволена **тільки** у `AgentTrace` — там це справді послідовність фаз.
- Порожній стан `ForesightPanel` — не «немає даних», а зміст: «Сьогодні вам нічого не потрібно» + один рядок причини (`silent_reason`). Це ключовий кадр демо, зроби його красивим.

### 10.2 Layout
```
┌────────────────────────────┬──────────────────────────┐
│  CartPanel                 │  AgentTrace (SSE)        │
│  ─ товари, сума, слот      │  фази 0..6, live         │
│  ─ WeatherBadge            │                          │
│                            │  ──────────────────────  │
│  SlotConflictCard (умовно) │  McpInspector            │
│                            │  RAW JSON-RPC, collapsed │
│  ForesightPanel            │                          │
│  ─ 0..3 SuggestionCard     │                          │
│  ─ «Додати все» / Undo     │                          │
└────────────────────────────┴──────────────────────────┘
DemoControls — плаваюча панель знизу: [Штиль][Циклон][Спека][Мороз] + [Скинути кошик]
```

### 10.3 `SuggestionCard`
Обов'язкові елементи: назва, ціна, **причина українською (≤90 символів)**, бейдж впевненості (`0.83` → «висока»), розгортання `evidence` списком, кнопки «Додати» / «Не треба» (dismiss шле `/agent/feedback`).

### 10.4 Undo
Після `apply` показати toast «Додано 2 товари» з дією «Скасувати» на 8 секунд → `silpo_remove_cart_products`.

---

## 11. Docker

`docker-compose.yml` сервіси: `web` (5173), `api` (8000), `worker`, `postgres` (5432), `redis` (6379).
`Makefile` цілі: `up`, `down`, `logs`, `migrate`, `seed`, `test`, `fmt`.
`make up` має піднімати робочий стенд однією командою з чистого клону після заповнення `.env`.

---

## 12. Порядок реалізації (виконуй строго по черзі, комітити після кожного кроку)

- [ ] **M0** Скелет: compose, FastAPI `/health`, Vite-застосунок, Tailwind, токени, `make up` працює.
- [ ] **M1** OAuth 2.1 + PKCE + DCR до `mcp.silpo.ua`, токени в Postgres під Fernet, `/auth/status` віддає ім'я Гостя.
- [ ] **M2** MCP-клієнт: `tools/list`, `call_tool` з trace/retry, `/cart` віддає реальний кошик у UI.
- [ ] **M3** `McpInspector` + `AgentTrace` на SSE. Тут уже має бути видно живі JSON-RPC виклики — **це вимога хакатону, не відкладай**.
- [ ] **M4** Weather: Open-Meteo forecast + archive, `climate_normals`, `WeatherDelta`, фікстури, `DemoControls`, `WeatherBadge`.
- [ ] **M5** Hazard-модель + нормалізація SKU + `Candidate`. Юніт-тести на синтетичній історії.
- [ ] **M6** Elasticity + priors yaml + scoring. Юніт-тести на монотонність (сильніший шок ⇒ не нижчий скор).
- [ ] **M7** Guardrails + `drop`-події в trace. Тест: лактозний Гість не отримує молочку **ніколи**.
- [ ] **M8** Reasoner (Claude, structured output) + валідація відповіді + детермінований fallback.
- [ ] **M9** `ForesightPanel`, `SuggestionCard`, `/agent/apply` (add_products) + Undo + верифікація кошика.
- [ ] **M10** Гілка конфлікту слоту: `SlotConflictCard`, `shift_slot` через `silpo_update_shopping_cart`.
- [ ] **M11** Feedback loop: `/agent/feedback`, `dismissed_ban`, `worker.py` T+72h evaluation на `silpo_get_my_offline_orders`.
- [ ] **M12** Порожній стан «Сьогодні вам нічого не потрібно» + сценарій «торт і свічки» (демо-фікстура кошика). Полірування UI.
- [ ] **M13** README з інструкцією запуску, скріншотами і посиланням на трейс. Експорт трейсу в `.ndjson` для журі.

---

## 13. Критерії приймання (DoD)

1. `make up` з чистого клону + заповненого `.env` піднімає стенд; логін через реальний акаунт Сільпо працює.
2. Зміна кошика автоматично (без кнопки) запускає агента через 20 с; у трейсі видно ≥14 різних `silpo_*` tools.
3. Сценарій «Циклон»: агент пропонує зсув слоту **і** 2 товари, кожен із причиною, що містить конкретне число з історії або погоди.
4. Сценарій «Торт і свічки» + мороз: агент повертає `status="silent"` з осмисленим `silent_reason`. Порожній стан відрендерено.
5. Гість із обмеженням «лактоза» не отримує жодного молочного кандидата; відповідний `drop` видно в трейсі.
6. Жодного токена в мережевих запитах фронтенду (перевіряється в DevTools).
7. `GET /trace/{run_id}?format=ndjson` віддає повний JSON-RPC лог, придатний для демонстрації.
8. Повний цикл агента ≤ 6 с на теплому кеші.

---

## 14. Anti-goals (не роби)

- Не давай LLM обирати або додавати товари — лише формулювати причини.
- Не викликай write-tools без явного кліку Гостя.
- Не створюй кошик автоматично, якщо `exists: false` — поверни `no_cart`.
- Не звертайся до жодних API Сільпо, крім `https://mcp.silpo.ua/mcp`.
- Не показуй більше 3 карток. Ніколи не заповнюй слоти заради заповнення.
- Не зберігай MCP-токени в localStorage, Zustand або будь-де на клієнті.
- Не додавай анімацій на кожну картку. Одна оркестрована поява результату — достатньо.
- Не вигадуй цифр у причинах. Кожна цифра має походити з `Evidence`.

---

## 15. Джерела

- MCP «Сільпо»: `https://mcp.silpo.ua/mcp` · документація: `https://ai-factory.silpo.ua/docs/mcp`
- MCP-специфікація: `https://modelcontextprotocol.io`
- Open-Meteo Forecast / Archive: `https://open-meteo.com/en/docs`
