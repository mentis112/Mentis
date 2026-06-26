# Architecture Overview

## 1. Recommended Architecture

The system is organized as a monorepo with clear separation between a React SPA and a Python API:

- `frontend`: React application for instructor workflows, localization, theme control, and dashboard UX
- `backend`: FastAPI application that owns authentication, persistence, provider integrations, upload processing, evaluation logic, quotas, and auditability
- `docs`: architecture and implementation references

The backend follows a layered architecture:

1. `api`: HTTP boundary and dependency wiring
2. `schemas`: request/response contracts
3. `services`: business rules
4. `repositories`: database access
5. `models`: SQLAlchemy entities
6. `adapters`: provider and external integrations
7. `utils`: shared helpers for prompts, storage, parsing, and token estimation

The frontend follows a feature-modular SPA architecture:

1. `app`: router, providers, global stores
2. `components`: reusable shared and layout primitives
3. `modules`: feature pages and local components by domain
4. `services`: typed API client calls
5. `i18n`: translation resources and configuration
6. `theme`: theme synchronization
7. `types`: API/domain types shared across modules

## 2. Full Folder Structure

```text
.
├── .env.example
├── README.md
├── backend
│   ├── README.md
│   ├── alembic
│   │   ├── env.py
│   │   └── versions
│   │       └── 20260313_0001_initial.py
│   ├── alembic.ini
│   ├── app
│   │   ├── adapters
│   │   │   └── ai
│   │   ├── api
│   │   │   └── v1
│   │   │       └── endpoints
│   │   ├── core
│   │   ├── db
│   │   ├── models
│   │   ├── repositories
│   │   ├── schemas
│   │   ├── services
│   │   ├── tests
│   │   └── utils
│   └── pyproject.toml
├── docs
│   └── architecture.md
└── frontend
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.ts
    ├── tsconfig.app.json
    ├── tsconfig.json
    ├── tsconfig.node.json
    ├── vite.config.ts
    └── src
        ├── app
        ├── components
        │   ├── layout
        │   └── shared
        ├── i18n
        │   └── locales
        ├── lib
        ├── modules
        │   ├── auth
        │   ├── dashboard
        │   ├── evaluations
        │   ├── groups
        │   ├── providers
        │   ├── settings
        │   └── submissions
        ├── services
        ├── theme
        └── types
```

## 3. Database Schema

### Base Tables

#### `instructors`

- `id`
- `username`
- `email` unique
- `password` stored as hash
- `encrypted_api_key` nullable legacy compatibility field
- `api_provider` nullable legacy compatibility field
- `created_at`
- `updated_at`

#### `assignment_groups`

- `id`
- `instructor_id`
- `name`
- `description`
- `grade_scale`
- `is_active`
- `created_at`
- `updated_at`

#### `evaluation_criteria`

- `id`
- `group_id`
- `name`
- `weight`
- `description`
- `is_manual`
- `sort_order`
- `created_at`
- `updated_at`

#### `submissions`

- `id`
- `group_id`
- `upload_batch_id`
- `file_path`
- `original_filename`
- `student_id`
- `status`
- `error_message`
- `created_at`
- `processed_at`

#### `evaluation_results`

- `id`
- `submission_id`
- `provider_config_id`
- `provider_name`
- `model_name`
- `evaluation_number`
- `is_latest`
- `total_ai_score`
- `final_adjusted_score`
- `ai_feedback`
- `raw_ai_response`
- `created_at`
- `updated_at`

#### `criterion_scores`

- `id`
- `result_id`
- `criterion_id`
- `ai_score`
- `manual_score`
- `feedback`
- `created_at`
- `updated_at`

### Supporting Tables

#### `ai_provider_configs`

- `id`
- `instructor_id`
- `provider_name`
- `encrypted_api_key`
- `model_name`
- `is_active`
- `is_default`
- `daily_request_limit`
- `monthly_request_limit`
- `max_files_per_batch`
- `max_file_size_mb`
- `max_tokens_per_request`
- `created_at`
- `updated_at`

#### `provider_usage_logs`

- `id`
- `instructor_id`
- `provider_config_id`
- `provider_name`
- `submission_id`
- `evaluation_result_id`
- `request_type`
- `tokens_input`
- `tokens_output`
- `files_count`
- `estimated_cost`
- `status`
- `error_message`
- `created_at`

#### `upload_batches`

- `id`
- `instructor_id`
- `group_id`
- `total_files`
- `accepted_files`
- `rejected_files`
- `status`
- `created_at`

#### `app_preferences`

- `id`
- `instructor_id`
- `language`
- `theme`
- `created_at`
- `updated_at`

#### `audit_logs`

- `id`
- `instructor_id`
- `action`
- `entity_type`
- `entity_id`
- `metadata_json`
- `created_at`

#### `manual_adjustment_history`

- `id`
- `criterion_score_id`
- `instructor_id`
- `previous_manual_score`
- `new_manual_score`
- `previous_feedback`
- `new_feedback`
- `created_at`

#### `submission_content_cache`

- `id`
- `submission_id`
- `extracted_text`
- `parser_status`
- `parser_error`
- `content_sha256`
- `created_at`
- `updated_at`

#### `auth_sessions`

- `id`
- `instructor_id`
- `refresh_token_hash`
- `user_agent`
- `ip_address`
- `expires_at`
- `revoked_at`
- `created_at`

## 4. Backend Module Design

### Auth

- JWT access/refresh strategy
- hashed passwords
- persisted refresh sessions for logout/revocation
- `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`

### Instructors / Preferences

- instructor identity is the root tenant boundary
- preferences are stored in `app_preferences`
- locale/theme are also reflected in frontend stores

### AI Providers

- provider configurations are many-to-one per instructor
- default provider resolution is centralized in `ProviderService`
- encrypted API key storage uses Fernet
- connection test requests are logged in `provider_usage_logs`

### Assignment Groups / Criteria

- rubric ownership is enforced at the query layer
- criteria weight cap is enforced during authoring
- exact 100 total is enforced before evaluation

### Uploads / Submissions

- upload batches track partial success
- each file is validated independently
- parse errors fail only the affected submission
- supported extensions: `pdf`, `docx`, `txt`

### Evaluations

- latest evaluation flag is versioned per submission
- provider responses are normalized before persistence
- manual-only criteria support feedback without AI score
- manual adjustments generate history records and audit logs

### Usage Limits / Audit Logs

- local instructor/provider limits are enforced before provider requests
- hard blocks create provider usage records with `blocked_limit`
- significant mutations create audit log entries

## 5. Frontend Module and Page Design

### Global App

- `AppProviders`: TanStack Query, theme, locale synchronization
- `useAuthStore`: tokens and instructor session
- `usePreferenceStore`: local language/theme persistence
- `AppShell`: sidebar + topbar + main content area

### Pages

#### Auth

- `LoginPage`
- `RegisterPage`

#### Dashboard

- KPI cards
- provider usage panel
- quick-action area

#### Groups

- `GroupsPage`: group creation + list
- `GroupDetailPage`: criterion create/edit/delete flow

#### Submissions

- upload form with group + files + student ID mapping
- submission list with status badges
- route to per-submission evaluation history

#### Evaluations

- `SubmissionEvaluationsPage`: list all versions + re-evaluate action
- `EvaluationDetailPage`: criterion-level review and manual adjustment submission

#### Providers

- provider creation form
- test connection action
- usage summary cards

#### Settings

- interface preference sync
- account summary card

## 6. AI Provider Abstraction

The backend isolates provider variability behind:

- `BaseAIProvider`
- `OpenAIProvider`
- `GeminiProvider`
- `DeepSeekProvider`
- `OllamaProvider`
- `ProviderAdapterFactory`

Shared provider contract:

- `test_connection(api_key, model_name)`
- `evaluate_submission(payload)`
- `estimate_limit_risk(payload, estimated_tokens)`
- `validate_provider_config(api_key, model_name)`

Normalized output contract:

- `total_score`
- `summary_feedback`
- `criterion_scores[]`
- `raw_response`
- `provider_name`
- `model_name`
- optional token usage

## 7. Quota and Limit Strategy

### Upload-Level Rules

- global batch count from environment
- provider-specific max batch count override
- allowed extension and MIME checks
- file size hard block before processing

### Provider-Level Rules

- daily request limit
- monthly request limit
- token estimate pre-check
- provider adapter risk estimate
- blocked-limit usage logs

### UX Rules

- partial batch success is preserved
- local validation failures are surfaced before provider calls
- provider failures keep raw messages out of logs that might reveal secrets

## 8. API Design

Implemented route families:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /groups`
- `POST /groups`
- `GET /groups/{id}`
- `PATCH /groups/{id}`
- `DELETE /groups/{id}`
- `GET /groups/{group_id}/criteria`
- `POST /groups/{group_id}/criteria`
- `PATCH /criteria/{id}`
- `DELETE /criteria/{id}`
- `GET /submissions`
- `GET /submissions/{id}`
- `POST /submissions/upload`
- `PATCH /submissions/{id}/status`
- `POST /submissions/{id}/evaluate`
- `POST /submissions/{id}/re-evaluate`
- `GET /submissions/{id}/evaluations`
- `GET /evaluations/{id}`
- `PATCH /evaluations/{id}/manual-adjustments`
- `GET /providers`
- `POST /providers`
- `PATCH /providers/{id}`
- `POST /providers/{id}/test`
- `GET /providers/usage`
- `GET /preferences`
- `PATCH /preferences`
- `GET /dashboard/summary`
- `GET /audit-logs`

## 9. Key Business Flows

### Provider Settings Flow

1. Instructor saves provider config.
2. API key is encrypted at write time.
3. Optional connection test logs success/failure.
4. Default active provider is used for evaluation unless explicitly overridden.

### Submission Upload Flow

1. Instructor selects group and files.
2. Backend validates extension, MIME, and batch constraints.
3. File is stored locally.
4. Content is parsed and cached.
5. Submission is marked `pending` or `failed` independently.

### Evaluation Execution Flow

1. Load submission, cached text, group, and criteria.
2. Ensure criteria total 100.
3. Resolve active provider config.
4. Estimate token risk and enforce quotas.
5. Build structured evaluation prompt.
6. Call adapter and normalize JSON output.
7. Store evaluation result and criterion scores.
8. Clear previous latest flag and mark new result latest.
9. Log provider usage and audit event.

### Manual Adjustment Flow

1. Open evaluation detail.
2. Display criterion breakdown.
3. Submit manual score and feedback updates.
4. Persist change history per criterion score.
5. Recalculate `final_adjusted_score`.

## 10. Theme and i18n Strategy

### Localization

- all principal UI labels live in `src/i18n/locales/en.json` and `ar.json`
- i18n state updates `lang` and `dir` on the document element
- Arabic mode switches layout to RTL immediately

### Theme

- theme preference stored in Zustand and synced through `ThemeProvider`
- CSS variables define shared semantic color tokens
- light and dark mode share the same component primitives

## 11. Implementation Roadmap

### Phase 1

- auth
- preferences
- provider settings
- groups
- criteria

### Phase 2

- uploads
- submissions
- file parsing
- evaluation pipeline
- evaluation history

### Phase 3

- manual adjustments
- dashboard analytics
- audit-log review
- usage-limit refinement
- retry/re-evaluation improvements

### Phase 4

- chunk splitting and bundle optimization
- backend tests and API contract tests
- queue integration abstraction for Celery/RQ
- S3/MinIO storage adapter
- richer analytics and filtering
