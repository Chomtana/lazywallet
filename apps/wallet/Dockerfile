# Wallet: static Vite build served at the root of $DOMAIN. Build context: repo root.
FROM node:24-alpine AS build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/wallet/package.json apps/wallet/
RUN pnpm install --frozen-lockfile --filter wallet
COPY apps/wallet apps/wallet

# Vite inlines these at build time; they point at the routes in docker-compose.yml.
ARG DOMAIN
ENV VITE_AGENT_WS_URL=wss://${DOMAIN}/lazy-agent/ws \
    VITE_SANDBOX_RPC_URL=https://${DOMAIN}/sandbox-eth \
    VITE_SANDBOX_AVAX_RPC_URL=https://${DOMAIN}/sandbox-avax \
    VITE_FAUCET_URL=https://${DOMAIN}/sandbox-faucet
RUN pnpm --filter wallet build

FROM caddy:2-alpine
COPY --from=build /app/apps/wallet/dist /srv
# SPA fallback for React Router's browser routes.
COPY <<'CADDY' /etc/caddy/Caddyfile
:80 {
	root * /srv
	try_files {path} /index.html
	file_server
}
CADDY
