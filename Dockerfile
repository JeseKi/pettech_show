FROM node:23-alpine AS builder
WORKDIR /app
ARG MIRROR_MODE=auto

COPY package.json pnpm-lock.yaml* ./
RUN set -eux; \
    mirror_mode="$MIRROR_MODE"; \
    if [ "$mirror_mode" = "auto" ]; then \
        if node -e "const c = new AbortController(); setTimeout(() => c.abort(), 3000); fetch('https://www.google.com/generate_204', { signal: c.signal }).then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1));"; then \
            mirror_mode="global"; \
        else \
            mirror_mode="cn"; \
        fi; \
    fi; \
    case "$mirror_mode" in \
        cn) \
            sed -i 's#https://dl-cdn.alpinelinux.org/alpine#https://mirrors.tuna.tsinghua.edu.cn/alpine#g' /etc/apk/repositories; \
            npm_registry="https://registry.npmmirror.com"; \
            ;; \
        global) \
            npm_registry="https://registry.npmjs.org"; \
            ;; \
        *) \
            echo "Unsupported MIRROR_MODE: $MIRROR_MODE"; \
            exit 1; \
            ;; \
    esac; \
    echo "Using mirror mode: $mirror_mode"; \
    npm config set registry "$npm_registry"; \
    COREPACK_NPM_REGISTRY="$npm_registry" corepack enable; \
    COREPACK_NPM_REGISTRY="$npm_registry" corepack install
RUN pnpm install --frozen-lockfile
COPY . .
COPY .env .
RUN pnpm run build

FROM node:23-slim AS opencode_cli
ARG MIRROR_MODE=auto
RUN set -eux; \
    mirror_mode="$MIRROR_MODE"; \
    if [ "$mirror_mode" = "auto" ]; then \
        if node -e "const c = new AbortController(); setTimeout(() => c.abort(), 3000); fetch('https://www.google.com/generate_204', { signal: c.signal }).then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1));"; then \
            mirror_mode="global"; \
        else \
            mirror_mode="cn"; \
        fi; \
    fi; \
    case "$mirror_mode" in \
        cn) \
            npm_registry="https://registry.npmmirror.com"; \
            ;; \
        global) \
            npm_registry="https://registry.npmjs.org"; \
            ;; \
        *) \
            echo "Unsupported MIRROR_MODE: $MIRROR_MODE"; \
            exit 1; \
            ;; \
    esac; \
    echo "Using mirror mode: $mirror_mode"; \
    npm config set registry "$npm_registry"; \
    npm install -g opencode-ai; \
    opencode --version

FROM python:3.11-slim
WORKDIR /app
ARG MIRROR_MODE=auto
COPY .env .
COPY requirements.txt .
RUN set -eux; \
    mirror_mode="$MIRROR_MODE"; \
    if [ "$mirror_mode" = "auto" ]; then \
        if python -c "import urllib.request; urllib.request.urlopen('https://www.google.com/generate_204', timeout=3).close()"; then \
            mirror_mode="global"; \
        else \
            mirror_mode="cn"; \
        fi; \
    fi; \
    case "$mirror_mode" in \
        cn) \
            . /etc/os-release; \
            printf 'Types: deb\nURIs: https://mirrors.tuna.tsinghua.edu.cn/debian\nSuites: %s %s-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: https://mirrors.tuna.tsinghua.edu.cn/debian-security\nSuites: %s-security\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' "$VERSION_CODENAME" "$VERSION_CODENAME" "$VERSION_CODENAME" > /etc/apt/sources.list.d/debian.sources; \
            pypi_index="https://pypi.tuna.tsinghua.edu.cn/simple"; \
            ;; \
        global) \
            pypi_index="https://pypi.org/simple"; \
            ;; \
        *) \
            echo "Unsupported MIRROR_MODE: $MIRROR_MODE"; \
            exit 1; \
            ;; \
    esac; \
    echo "Using mirror mode: $mirror_mode"; \
    apt-get update; \
    apt-get install -y --no-install-recommends tmux bash; \
    rm -rf /var/lib/apt/lists/*; \
    pip install --no-cache-dir --index-url "$pypi_index" uv; \
    uv pip install --no-cache-dir --index-url "$pypi_index" -r requirements.txt --system

COPY src/server/ ./src/server/
COPY .agents ./.agents
COPY config ./config
COPY --from=opencode_cli /usr/local/lib/node_modules/opencode-ai/bin/opencode.exe /usr/local/bin/opencode
COPY --from=builder /app/dist ./dist
COPY run.py .
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x /app/entrypoint.sh /usr/local/bin/opencode

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
