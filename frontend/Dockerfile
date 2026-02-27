# Dockerfile — AEP frontend (React + Vite → nginx)
# Two-stage: Node builds static assets, nginx serves them.
# VITE_* vars are baked in at build time (Vite limitation).
# Backend proxy URL is injected at runtime via BACKEND_URL env var.
#
# IMPORTANT: Build context must be repository root (not frontend/)
# Usage: docker build -f frontend/Dockerfile .
# This allows copying both frontend/ and packages/ directories

# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

# Set workdir to parent so we can copy both frontend and packages as siblings
WORKDIR /build

# Copy frontend package.json for dependency installation
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /build/frontend
RUN npm install --prefer-offline

# Copy frontend source and shared packages
WORKDIR /build
COPY frontend/ ./frontend/
COPY packages/ ./packages/

# Build-time env vars (Vite bakes these into the JS bundle).
# WARNING: Defaults point to localhost — only valid for local dev builds.
# Always override via --build-arg for staging/production, e.g.:
#   docker buildx build --build-arg VITE_CORE_API=https://staging.navralabs.com ...
ARG VITE_CORE_API=http://localhost:8787
ARG VITE_API_BASE_URL=http://localhost:8787
ARG VITE_NAVI_BACKEND_URL=http://localhost:8787
ARG VITE_ORG_ID=default
ARG VITE_USER_ID=default_user

ARG NODE_ENV=development
ENV VITE_CORE_API=$VITE_CORE_API \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_NAVI_BACKEND_URL=$VITE_NAVI_BACKEND_URL \
    VITE_ORG_ID=$VITE_ORG_ID \
    VITE_USER_ID=$VITE_USER_ID \
    NODE_ENV=$NODE_ENV

# Fail fast: refuse to build a production image baked with localhost URLs.
RUN if [ "$NODE_ENV" = "production" ] && echo "$VITE_CORE_API" | grep -qiE "localhost|127\.0\.0\.1|0\.0\.0\.0"; then \
      echo "ERROR: VITE_CORE_API points to a local address while NODE_ENV=production. Pass --build-arg VITE_CORE_API=https://..."; \
      exit 1; \
    fi

# Build from frontend directory
WORKDIR /build/frontend
RUN npm run build

# ── Stage 2: serve ───────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# nginx config template — BACKEND_URL is substituted at container start
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy Vite build output
COPY --from=builder /build/frontend/dist /usr/share/nginx/html

# nginx official image auto-runs envsubst on /etc/nginx/templates/*.template
# and writes the result to /etc/nginx/conf.d/ before nginx starts.
# Set default so the image works standalone without --env.
ENV BACKEND_URL=http://localhost:8787

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
