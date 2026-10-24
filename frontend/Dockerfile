FROM node:22-alpine AS build
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /w
COPY package.json package-lock.json ./
RUN npm config set registry $NPM_REGISTRY && npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /w/out /srv
COPY Caddyfile /etc/caddy/Caddyfile
