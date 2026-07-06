# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/digital-twin-dashboard/package*.json ./
RUN npm ci
COPY frontend/digital-twin-dashboard/ ./
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# Stage 2: Setup the python backend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (e.g. libgomp1 is needed for LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files, models, and datasets
COPY backend/ ./backend/
COPY models/ ./models/
COPY dataset/ ./dataset/

# Copy the built frontend from Stage 1 into the backend's directory structure
COPY --from=frontend-builder /app/frontend/dist /app/frontend/digital-twin-dashboard/dist

# Expose port and define run command
EXPOSE 8000
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

# Initialize DB and start backend
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
