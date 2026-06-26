# Automated Project Evaluation System

## One-command startup for teammates

Prerequisite: install and open Docker Desktop.

From the project root:

```powershell
docker compose up --build
```

Open the app:

```text
http://localhost:5173
```

Demo login created automatically on first startup:

```text
Email: demo@mentis.dev
Password: DemoPass123!
```

The command starts PostgreSQL, runs backend migrations, creates the demo user if it does not already exist, starts the FastAPI backend on `http://localhost:8000`, and starts the Vite frontend on `http://localhost:5173`.

To stop the project:

```powershell
docker compose down
```

To delete the local Docker database and uploaded files for a clean start:

```powershell
docker compose down -v
```

منصة تقييم مشاريع للمدرسين مبنية بـ React + Vite في الواجهة، و FastAPI + PostgreSQL في الخلفية.

## قبل الرفع على GitHub

لا ترفعي الملفات المحلية أو السرية. هذا المشروع يحتوي على `.gitignore` يستبعد تلقائيا:

- ملفات الأسرار: `.env`, `backend/.env`, `frontend/.env`
- مكتبات الواجهة: `frontend/node_modules`
- بيئات Python: `.venv`, `.venv-win`, `venv`, `backend/.venv`
- ملفات التشغيل واللوج: `.run`, `*.log`, `*.pid`
- ملفات الطلاب المرفوعة داخل `uploads`
- ملفات PostgreSQL المحلية مثل `.pgdata`

ارفعي المشروع باستخدام Git حتى يتم احترام `.gitignore`:

```powershell
git init
git add .
git commit -m "Initial project"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

## المتطلبات

- Git
- Node.js 20 أو أحدث
- Python 3.10 أو أحدث
- Docker Desktop لتشغيل PostgreSQL بسهولة

## التشغيل بعد تحميل المشروع

### 1. تحميل المشروع

```powershell
git clone https://github.com/YOUR_USER/YOUR_REPO.git
cd YOUR_REPO
```

### 2. تشغيل قاعدة البيانات

شغلي Docker Desktop أولا، ثم من مجلد المشروع:

```powershell
docker compose up -d postgres
```

قاعدة البيانات الافتراضية:

- Host: `localhost`
- Port: `5432`
- Database: `project_eval`
- User: `postgres`
- Password: `postgres`

### 3. تجهيز Backend

من مجلد المشروع:

```powershell
Copy-Item backend\.env.example backend\.env
cd backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .
```

بعد تثبيت المكتبات، ولتغيير مفتاح التشفير في `backend/.env`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

انسخي الناتج إلى قيمة `API_KEY_ENCRYPTION_KEY` داخل `backend/.env`.

لإنشاء مفاتيح JWT اختياريا:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

ضعي ناتجين مختلفين في:

- `JWT_SECRET_KEY`
- `JWT_REFRESH_SECRET_KEY`

ثم شغلي migrations:

```powershell
alembic upgrade head
```

وشغلي خادم الـ API:

```powershell
uvicorn app.main:app --reload
```

الرابط المتوقع:

```text
http://localhost:8000/api/v1/health
```

### 4. تجهيز Frontend

افتحي Terminal ثاني من مجلد المشروع:

```powershell
Copy-Item frontend\.env.example frontend\.env
cd frontend
npm ci
npm run dev
```

الرابط المتوقع:

```text
http://localhost:5173
```

## ملاحظات مهمة

- لا ترفعي ملفات `.env` على GitHub. ارفعي فقط ملفات `.env.example`.
- لا ترفعي `node_modules` أو أي مجلد `.venv`.
- `uploads` مخصص لملفات التشغيل فقط. لو أردتن مشاركة بيانات وتجارب قديمة، ستحتجن أيضا إلى نسخة من قاعدة البيانات، وليس مجلد `uploads` فقط.
- إذا كان منفذ PostgreSQL `5432` مستخدما على جهازك، غيري المنفذ في `docker-compose.yml` وفي `DATABASE_URL` داخل `backend/.env`.

## أوامر مفيدة

إيقاف قاعدة البيانات:

```powershell
docker compose down
```

إيقاف قاعدة البيانات مع حذف بياناتها المحلية:

```powershell
docker compose down -v
```

فحص الـ API:

```powershell
curl http://localhost:8000/api/v1/health
```
