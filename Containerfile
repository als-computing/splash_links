# ---- stage 1: build the React frontend ----
FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---- stage 2: resolve and install the pixi environment ----
FROM ghcr.io/prefix-dev/pixi:0.63.2 AS pixi-build

WORKDIR /app

# Copy only the files pixi needs first so layer cache is reused on code-only changes.
COPY pixi.toml pyproject.toml ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

RUN pixi install

# ---- stage 3: lean runtime image ----
FROM debian:bookworm-slim AS runtime

WORKDIR /app

# Bring across the resolved environment (conda + pypi) but not the pixi toolchain.
COPY --from=pixi-build /app/.pixi/envs/default /app/.pixi/envs/default
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Copy the built frontend so FastAPI can serve it as static files.
COPY --from=frontend-build /frontend/dist /app/frontend/dist

ENV PATH="/app/.pixi/envs/default/bin:$PATH"
ENV SPLASH_LINKS_STATIC_DIR="/app/frontend/dist"

EXPOSE 8080

CMD ["uvicorn", "splash_links.main:app", "--host", "0.0.0.0", "--port", "8080"]

LABEL Name="splash-links" \
      Version="0.1.0" \
      Description="Entity link graph service" \
      Maintainer="als-computing"
