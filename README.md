# Human Digital Twin AI Platform (Production-Oriented)

This repository now contains a modular, production-style full-stack **Human Digital Twin platform** for personal wellness optimization with:

- JWT authentication + secure sessions
- Profile-driven personalization
- Daily logs + food/macronutrient logging
- Ensemble ML inference (Logistic, RF, XGBoost, LightGBM, Neural Net)
- Cluster-based personalization
- Time-series forecasting (7-day future wellness)
- What-if simulation
- Advanced dashboard analytics (weekly/monthly trends, anomalies, habit impact)

## Folder Structure

```text
human-digital-twin/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   ├── ml/
│   │   │   ├── feature_engineering.py
│   │   │   ├── recommendation.py
│   │   │   ├── timeseries.py
│   │   │   ├── training.py
│   │   │   └── engine.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── profile.py
│   │   │   ├── daily_logs.py
│   │   │   ├── nutrition.py
│   │   │   ├── predictions.py
│   │   │   ├── dashboard.py
│   │   │   └── ml_ops.py
│   │   └── services/
│   │       ├── analytics.py
│   │       └── nutrition.py
│   ├── artifacts/
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   └── digital-twin-dashboard/
│       ├── src/
│       │   ├── api.js
│       │   ├── auth-context.jsx
│       │   ├── App.jsx
│       │   ├── components/
│       │   │   ├── AppLayout.jsx
│       │   │   └── ProtectedRoute.jsx
│       │   └── pages/
│       │       ├── LoginPage.jsx
│       │       ├── SignupPage.jsx
│       │       ├── ProfilePage.jsx
│       │       └── DashboardPage.jsx
│       └── package.json
├── dataset/
├── models/
└── README.md
```

## Database Design (PostgreSQL-Ready)

Defined in `backend/app/models.py` via SQLAlchemy ORM:

- `users`: identity + hashed password
- `user_sessions`: JWT session tracking (`jti`, expiry, revoke state)
- `profiles`: static twin profile (age, gender, body metrics, food pattern, conditions, goal)
- `daily_logs`: dynamic daily health/wellness inputs
- `food_logs`: meal-wise nutrition + macros
- `predictions`: prediction history, model outputs, recommendations, what-if scenarios
- `model_metrics`: model training/evaluation snapshots

`DATABASE_URL` defaults to PostgreSQL format. If unavailable, the app falls back to local SQLite for development continuity.

## API Endpoints

Base prefix: `/api/v1`

### Auth
- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

### Profile
- `GET /profile`
- `PUT /profile`

### Daily Logs
- `POST /daily-logs` (upsert by date)
- `PATCH /daily-logs/{log_date}`
- `GET /daily-logs`

### Nutrition
- `POST /nutrition/logs`
- `GET /nutrition/logs`
- `GET /nutrition/summary/{log_date}`

### Predictions
- `POST /predictions/run`
- `POST /predictions/simulate` (what-if)
- `GET /predictions/history`
- `GET /predictions/forecast`

### Dashboard Analytics
- `GET /dashboard/overview`
- `GET /dashboard/anomalies`
- `GET /dashboard/habit-impact`
- `GET /dashboard/trends`

### ML Ops
- `POST /ml/train`
- `GET /ml/metrics`

## ML Integration Overview

Implemented in `backend/app/ml/`:

- Feature engineering:
  - BMI auto-calculation
  - Activity ratio
  - Sleep quality score
- Models:
  - Logistic Regression
  - Random Forest
  - XGBoost (if installed)
  - LightGBM (if installed)
  - MLP Neural Network
- Personalization:
  - Cluster-based models using KMeans + cluster-specific RF
- Forecasting:
  - LSTM-based sequence model (TensorFlow when available)
  - Weighted moving-average fallback for low-resource/runtime-safe use
- Recommendation engine:
  - Rule-based + ML-confidence-aware hybrid recommendations

## Frontend Features

Implemented with React + Vite + Tailwind + Recharts:

- Login / Signup pages
- Protected routes
- Profile management page
- Dashboard:
  - Current vs predicted twin state
  - Daily log input and prediction trigger
  - What-if simulation
  - Weekly/monthly trends
  - Forecast charts
  - Anomaly detection display
  - Habit impact chart
  - Nutrition logging and macro summaries

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend/digital-twin-dashboard
npm install
npm run dev
```

### Environment Variables (Recommended)

- `DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<db>`
- `JWT_SECRET_KEY=<strong-random-secret>`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120`
- `CORS_ORIGINS=http://localhost:5173`
- `VITE_API_BASE_URL=http://localhost:8000/api/v1`

## Deployment (Suggested)

- Frontend: Vercel / Netlify
- Backend: Render / Railway / Fly.io
- Database: PostgreSQL (Neon / Supabase / Railway Postgres)

## Notes

- Advanced optional features such as chatbot assistant, gamification badges/streaks, and wearable connectors are now straightforward extensions over this modular architecture.
- First training run can be triggered with `POST /api/v1/ml/train`.
