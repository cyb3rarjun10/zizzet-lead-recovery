# ⚡ Zizzet AI Lead Recovery Engine

A high-performance, multi-tenant FastAPI backend service that analyzes inactive and high-intent sales leads, evaluates customer conversation history with Google Gemini LLM, and produces structured recovery recommendations with personalized follow-ups.

---

## 🎯 System Architecture

```text
Incoming Request / Webhook
          │
          ▼
┌──────────────────┐
│  FastAPI Gateway │ ──(Header / Payload Tenant Scoping)
└────────┬─────────┘
         │
         ├───► [Sync Endpoints: /analyze, /{id}/analysis, /{id}/follow-up]
         │          │
         │          ▼
         │     ┌────────────────────────────────────────────────────────┐
         │     │ Lead Recovery Service                                  │
         │     │  • Deterministic Opt-Out Scanner (Regex 'STOP' guard)  │
         │     │  • Google Gemini LLM (Structured JSON Schema)          │
         │     │  • Pydantic v2 Output Validation                       │
         │     └────────────────────────┬───────────────────────────────┘
         │                              │
         │                              ▼
         │                     [(PostgreSQL / SQLite)]
         │                      • Multi-Tenant Foreign Keys
         │                      • Scoped Unique Constraints
         │
         └───► [Async Webhook: /webhooks/leads]
                    │
                    ▼
               ┌────────────────────────────────────────────────────────┐
               │ Idempotency Guard (uq_tenant_idempotency)              │
               │  • Duplicate check (returns 202 duplicate_ignored)     │
               │  • Background Worker queue via FastAPI BackgroundTasks │
               └────────────────────────────────────────────────────────┘


## 💻 Tech Stack & Key Decisions

* **Framework:** Python 3.10+ / FastAPI

  * High throughput
  * Async-native
  * Automated Swagger documentation at `/docs`

* **Database:** SQLite for local development / PostgreSQL-ready

  * SQLAlchemy 2.0
  * Strict foreign key constraints
  * Per-tenant composite indices

* **LLM Engine:** Google Gemini API

  * Direct REST payload
  * Enforced `responseMimeType: "application/json"`

* **Validation:** Strict Pydantic v2 schemas

  * Request payload validation
  * Data sanitization
  * Structured AI response validation

* **Background Jobs:** FastAPI `BackgroundTasks`

  * Backed by a persistent `WebhookEvent` state store
  * State flow:
    `pending` → `processing` → `completed` / `failed`

* **Testing:** `pytest` and `TestClient`

  * Verifies all 5 business cases
  * Verifies multi-tenant security barriers

---

## 📁 Repository Structure

```text
zizzet-lead-recovery/
├── app/
│   ├── api/
│   │   ├── deps.py              # Tenant extraction & session injection
│   │   └── v1/
│   │       ├── leads.py         # /analyze, /{lead_id}/analysis, /{lead_id}/follow-up
│   │       └── webhooks.py      # /webhooks/leads (async + idempotency)
│   ├── core/
│   │   └── config.py            # Pydantic BaseSettings environment loader
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine & session factory
│   │   └── models.py            # Tenant, Lead, LeadAnalysis, WebhookEvent models
│   ├── schemas/
│   │   ├── analysis.py          # Strict Pydantic model for structured AI outputs
│   │   └── lead.py              # Input request & webhook schemas
│   ├── services/
│   │   ├── llm_service.py       # Google Gemini REST integration
│   │   ├── lead_service.py      # Deterministic opt-out scanner & prompt engine
│   │   └── recovery_worker.py   # Async background task worker
│   └── main.py                  # App entry point, CORS, and routing
├── tests/
│   ├── conftest.py              # In-memory test database fixture
│   └── test_evaluation_cases.py # Comprehensive test suite for Cases A-E
├── .env.example                 # Example configuration
├── requirements.txt             # Project dependencies
├── pytest.ini                   # Test configuration
└── README.md
```

---

## 🚀 Quickstart & Local Setup

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/<YOUR_USERNAME>/zizzet-lead-recovery.git
cd zizzet-lead-recovery

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` and add your Gemini API key:

```env
PROJECT_NAME="Zizzet AI Lead Recovery Engine"
API_V1_PREFIX="/api/v1"
DATABASE_URL="sqlite:///./lead_recovery.db"
LLM_PROVIDER="gemini"
GEMINI_API_KEY="AIzaSy..."
```

> **Security:** Never commit your actual `.env` file or Gemini API key to Git.

### 3. Run the Application

```bash
uvicorn app.main:app --reload --port 8000
```

Available endpoints:

* Interactive Swagger API Documentation: `http://localhost:8000/docs`
* Health check: `http://localhost:8000/health`

### 4. Run Automated Tests

```bash
pytest -v
```

---

## 🗄️ Database Design & Multi-Tenancy

Every database table is scoped by `tenant_id`. Data leakages between different tenants are physically prevented at the database layer via composite constraints.

### `tenants`

| Column       | Type         | Constraints               | Description                |
| ------------ | ------------ | ------------------------- | -------------------------- |
| `id`         | VARCHAR(64)  | PRIMARY KEY               | Unique business identifier |
| `name`       | VARCHAR(128) | NOT NULL                  | Tenant business name       |
| `created_at` | DATETIME     | DEFAULT CURRENT_TIMESTAMP | Registration timestamp     |

### `leads`

| Column             | Type         | Constraints                          | Description                    |
| ------------------ | ------------ | ------------------------------------ | ------------------------------ |
| `id`               | INTEGER      | PRIMARY KEY, AUTOINCREMENT           | Internal Lead surrogate ID     |
| `tenant_id`        | VARCHAR(64)  | FOREIGN KEY (`tenants.id`), NOT NULL | Parent tenant ID               |
| `external_lead_id` | VARCHAR(128) | NOT NULL, INDEXED                    | External ID (e.g. `lead_1024`) |
| `customer_name`    | VARCHAR(128) | NULLABLE                             | Contact name                   |
| `customer_phone`   | VARCHAR(32)  | NULLABLE                             | Contact phone                  |
| `source`           | VARCHAR(64)  | DEFAULT `'whatsapp'`                 | Origin source                  |
| `status`           | VARCHAR(64)  | DEFAULT `'contacted'`                | Funnel status                  |
| `do_not_contact`   | BOOLEAN      | DEFAULT FALSE                        | Opt-out indicator              |

**Composite Unique Constraint:**

```python
UniqueConstraint("tenant_id", "external_lead_id")
```

This ensures a lead ID is unique per tenant, allowing separate tenants to use identical external lead IDs without collision.

### `lead_analyses`

| Column              | Type        | Constraints                        | Description                       |
| ------------------- | ----------- | ---------------------------------- | --------------------------------- |
| `id`                | INTEGER     | PRIMARY KEY, AUTOINCREMENT         | Analysis record ID                |
| `lead_id`           | INTEGER     | FOREIGN KEY (`leads.id`), NOT NULL | Scoped Lead reference             |
| `tenant_id`         | VARCHAR(64) | NOT NULL, INDEXED                  | Tenant ID                         |
| `lead_score`        | INTEGER     | NOT NULL (0-100)                   | AI-derived intent score           |
| `priority`          | VARCHAR(32) | NOT NULL (`high`, `medium`, `low`) | Follow-up priority                |
| `intent`            | VARCHAR(64) | NOT NULL                           | Detected customer intent          |
| `stage`             | VARCHAR(64) | NOT NULL                           | Funnel stage                      |
| `summary`           | TEXT        | NOT NULL                           | Overview of customer conversation |
| `next_best_action`  | TEXT        | NOT NULL                           | Actionable next step              |
| `follow_up_channel` | VARCHAR(32) | DEFAULT `'whatsapp'`               | Recommended channel               |
| `follow_up_message` | TEXT        | NULLABLE                           | Personalized outreach copy        |
| `do_not_contact`    | BOOLEAN     | DEFAULT FALSE                      | Contact suppression flag          |

### `webhook_events`

| Column            | Type         | Constraints                                    | Description             |
| ----------------- | ------------ | ---------------------------------------------- | ----------------------- |
| `id`              | INTEGER      | PRIMARY KEY, AUTOINCREMENT                     | Event surrogate ID      |
| `tenant_id`       | VARCHAR(64)  | NOT NULL, INDEXED                              | Tenant ID               |
| `idempotency_key` | VARCHAR(128) | NOT NULL, INDEXED                              | Unique event ID         |
| `status`          | VARCHAR(32)  | `pending`, `processing`, `completed`, `failed` | Execution state         |
| `payload`         | TEXT         | NOT NULL                                       | Stored raw JSON payload |
| `error_message`   | TEXT         | NULLABLE                                       | Logged failure trace    |

**Composite Unique Constraint:**

```python
UniqueConstraint("tenant_id", "idempotency_key")
```

This provides database-level deduplication.

---

## 📡 API Endpoints

All endpoints support tenant identification via the `X-Tenant-ID` header.

### 1. Synchronous Lead Analysis

```http
POST /api/v1/leads/analyze
```

* Analyzes customer conversation history
* Triggers opt-out scanning
* Calls the Gemini LLM
* Persists the analysis
* Returns structured data

### 2. Retrieve Latest Analysis

```http
GET /api/v1/leads/{lead_id}/analysis
```

* **Header:** `X-Tenant-ID: <tenant_id>`
* Fetches the most recent recovery recommendation for the given lead.
* Returns `404` if accessed by a different tenant.

### 3. Dispatch Follow-up

```http
POST /api/v1/leads/{lead_id}/follow-up
```

* **Header:** `X-Tenant-ID: <tenant_id>`
* Simulates dispatching the follow-up message to the customer.
* Fails with `400 Bad Request` if the customer has opted out (`do_not_contact=True`).

### 4. Asynchronous Webhook Receiver

```http
POST /api/v1/webhooks/leads
```

* Immediately validates the payload and acknowledges receipt with `202 Accepted`.
* Dispatches analysis to a background worker.
* Rejects duplicate `event_id` submissions with `202 Accepted` and status `duplicate_ignored`.

---

## 🧪 Evaluation Test Cases Verification

All 5 assignment evaluation scenarios are programmatically tested in:

```text
tests/test_evaluation_cases.py
```

| Case       | Scenario                                         | Expected Behavior                                                                  | Automated Test Status |
| ---------- | ------------------------------------------------ | ---------------------------------------------------------------------------------- | --------------------- |
| **Case A** | 50 employees + asks for pricing                  | `priority: "high"`, `lead_score >= 70`, actionable pricing follow-up               | ✅ PASS                |
| **Case B** | Asks only what the product does                  | `priority: "low"`, `lead_score <= 50`, discovery follow-up                         | ✅ PASS                |
| **Case C** | Requests a demo or call tomorrow                 | `next_best_action` recommends scheduling demo / calendar call                      | ✅ PASS                |
| **Case D** | Customer says: *"STOP. Don't message me again."* | `do_not_contact: True`, `follow_up_message: None`, follow-up endpoint blocked      | ✅ PASS                |
| **Case E** | Same webhook event submitted twice               | First returns `accepted`, second returns `duplicate_ignored` without re-processing | ✅ PASS                |

Run the automated suite with:

```bash
pytest -v
```

---

## 🛡️ Business Logic & Error Handling

### 1. Opt-Out Safety Guardrail

* A regex-based deterministic scanner intercepts keywords:

  * `STOP`
  * `UNSUBSCRIBE`
  * `DON'T MESSAGE`
  * `REMOVE ME`
* The scanner runs before or alongside LLM execution.
* If triggered:

  * `do_not_contact=True`
  * `follow_up_message=None`
  * `lead_score=0`
* This prevents unwanted outreach even if an LLM hallucinates.

### 2. Idempotency Guarantee

* Webhook submissions use an event identifier (`event_id`).
* If a duplicate event arrives, the database composite constraint and worker lock immediately skip task queueing.

### 3. Multi-Tenant Isolation

* Endpoints require tenant context via:

  * `X-Tenant-ID` header, or
  * Payload
* All queries filter strictly on both:

  * `tenant_id`
  * `external_lead_id`
* Cross-tenant record leakage returns a standard `404 Not Found`.

---

## ⚖️ Assumptions & Limitations

### Channel Integrations

Messaging delivery (WhatsApp / SMS) is simulated via a mock provider interface rather than connecting a live WhatsApp Business API account.

### Queue Implementation

The application uses FastAPI `BackgroundTasks` with persistent database event state tracking.

In high-volume production deployments with tens of thousands of requests per second, this can be transitioned to Redis + Celery/ARQ without changing the service interface.

---

## ✅ How to Check That It Works

1. Save this file as `README.md` in the project root.
2. Verify it is located next to `app/` and `tests/`:

```bash
ls -la README.md
```
