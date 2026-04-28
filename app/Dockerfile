# Specodex production image
# Multi-stage build: frontend static assets + backend API in one container

# ── Stage 1: Install all dependencies ────────────────────────────
FROM node:18-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json ./
COPY backend/package.json ./backend/
COPY frontend/package.json ./frontend/
COPY infrastructure/package.json ./infrastructure/

RUN npm ci

# ── Stage 2: Build frontend ─────────────────────────────────────
FROM deps AS build-frontend
COPY frontend/ ./frontend/

# Empty VITE_API_URL so frontend uses relative URLs (same-origin in production)
ENV VITE_API_URL=""
RUN npm run build:frontend

# ── Stage 3: Build backend ──────────────────────────────────────
FROM deps AS build-backend
COPY backend/ ./backend/
RUN npm run build:backend

# ── Stage 4: Production runtime ─────────────────────────────────
FROM node:18-alpine AS production

RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

WORKDIR /app

# Install production-only dependencies
COPY package.json package-lock.json ./
COPY backend/package.json ./backend/
COPY frontend/package.json ./frontend/
COPY infrastructure/package.json ./infrastructure/
RUN npm ci --omit=dev && npm cache clean --force

# Copy compiled backend
COPY --from=build-backend /app/backend/dist ./backend/dist

# Copy frontend static assets
COPY --from=build-frontend /app/frontend/dist ./public

ENV NODE_ENV=production
ENV PORT=3001
EXPOSE 3001

USER appuser

CMD ["node", "backend/dist/index.js"]
