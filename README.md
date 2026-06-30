# Automated Project Evaluation System

منصة تقييم مشاريع للمدرسين مبنية بواجهة React + Vite وخلفية FastAPI + PostgreSQL.

## التشغيل بأمر واحد

المتطلب الأساسي: تثبيت Docker Desktop وتشغيله.

من مجلد المشروع الرئيسي:

```powershell
docker compose up --build
```

افتح التطبيق:

```text
http://localhost:5173
```

حساب تجريبي يتم إنشاؤه تلقائيًا عند أول تشغيل:

```text
Email: demo@mentis.dev
Password: DemoPass123!
```

الأمر يشغّل PostgreSQL، يطبق migrations، ينشئ المستخدم التجريبي إذا لم يكن موجودًا، يشغّل FastAPI على:

```text
http://localhost:8000
```

ويشغّل الواجهة على:

```text
http://localhost:5173
```

لفحص الـ API:

```powershell
curl http://localhost:8000/api/v1/health
```

## إيقاف المشروع

```powershell
docker compose down
```

لإيقاف المشروع وحذف بيانات Docker المحلية:

```powershell
docker compose down -v
```

## ملاحظات قبل الرفع على GitHub

لا ترفع ملفات التشغيل المحلية أو الأسرار. المشروع يتجاهل تلقائيًا:

- ملفات البيئة: `.env`, `backend/.env`, `frontend/.env`
- مجلدات الاعتماد: `frontend/node_modules`
- مخرجات البناء: `frontend/dist`
- بيئات Python: `.venv`, `venv`, `backend/.venv`
- ملفات التشغيل واللوج: `.run`, `*.log`, `*.pid`
- ملفات الطلاب المرفوعة داخل `uploads`
- بيانات PostgreSQL المحلية مثل `.pgdata`
- بيانات وتجارب محلية داخل `test-data`

الملفات التي يجب رفعها هي كود التطبيق، إعدادات Docker، migrations، وملفات `.env.example` فقط.

## رفع النسخة

بعد مراجعة الملفات:

```powershell
git status
git add .
git commit -m "Update project evaluation app"
git push origin main
```

إذا كان الفرع المحلي ليس `main`:

```powershell
git branch -M main
git push -u origin main
```
