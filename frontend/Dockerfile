FROM node:22-alpine AS build
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /w
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm config set registry $NPM_REGISTRY && npm ci --include=optional --no-audit --fetch-retries=1 --fetch-timeout=600000
COPY . .
RUN --mount=type=cache,target=/root/.cache/next-swc npm run build

# Rebuild the stable proxy with patched Go and dependency versions.
FROM caddy:builder-alpine@sha256:ef9b65adf9a224770c6d5f6d1ae1bf99bc3caaa78d8c4bae3ea949ee6984f301 AS proxy-build
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    xcaddy build v2.11.7 --replace github.com/go-chi/chi/v5=github.com/go-chi/chi/v5@v5.4.0 \
    --replace golang.org/x/net=golang.org/x/net@v0.60.0 \
    --replace golang.org/x/crypto=golang.org/x/crypto@v0.58.0 --output /usr/bin/caddy

FROM caddy:2-alpine@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f
RUN apk upgrade --no-cache brotli-libs
COPY --from=proxy-build /usr/bin/caddy /usr/bin/caddy
COPY --from=build /w/out /srv
COPY Caddyfile /etc/caddy/Caddyfile

COPY --from=build /w/security-headers.caddy /etc/caddy/security-headers.caddy
