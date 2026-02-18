# Dockerfile — AEP frontend (React + Vite → nginx)
# Two-stage: Node builds static assets, nginx serves them.
# VITE_* vars are baked in at build time (Vite limitation).
# Backend proxy URL is injected at runtime via BACKEND_URL env var.

# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first (layer-cache friendly)
COPY package.json package-lock.json ./
RUN npm install --prefer-offline

# Copy source
COPY . .

# Build-time env vars (Vite bakes these into the JS bundle)
ARG VITE_CORE_API=http://localhost:8787
ARG VITE_API_BASE_URL=http://localhost:8787
ARG VITE_NAVI_BACKEND_URL=http://localhost:8787
ARG VITE_ORG_ID=default
ARG VITE_USER_ID=default_user

ENV VITE_CORE_API=$VITE_CORE_API \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_NAVI_BACKEND_URL=$VITE_NAVI_BACKEND_URL \
    VITE_ORG_ID=$VITE_ORG_ID \
    VITE_USER_ID=$VITE_USER_ID

RUN npm run build

# ── Stage 2: serve ───────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# nginx config template — BACKEND_URL is substituted at container start
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx official image auto-runs envsubst on /etc/nginx/templates/*.template
# and writes the result to /etc/nginx/conf.d/ before nginx starts.
# Set default so the image works standalone without --env.
ENV BACKEND_URL=http://localhost:8787

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
