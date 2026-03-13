# ---- build stage: resolve and install the pixi environment ----
FROM ghcr.io/prefix-dev/pixi:0.63.2 AS build

WORKDIR /app

# Copy only the files pixi needs first so layer cache is reused on code-only changes.
COPY pixi.toml pyproject.toml ./
COPY src/ src/

RUN pixi install

# ---- runtime stage: lean image with just the resolved env ----
FROM debian:bookworm-slim AS runtime

WORKDIR /app

# Bring across the resolved environment (conda + pypi) but not the pixi toolchain.
COPY --from=build /app/.pixi/envs/default /app/.pixi/envs/default
COPY src/ src/

ENV PATH="/app/.pixi/envs/default/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "splash_links.main:app", "--host", "0.0.0.0", "--port", "8080"]

LABEL Name="splash-links" \
      Version="0.1.0" \
      Description="Entity link graph service" \
      Maintainer="als-computing"