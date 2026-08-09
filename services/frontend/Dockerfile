FROM node:20-trixie-slim AS deps
ARG NPM_VERSION=10.9.4
RUN npm install -g npm@${NPM_VERSION}

WORKDIR /app/services/frontend

COPY services/frontend/package.json services/frontend/package-lock.json ./
RUN npm ci

FROM node:20-trixie-slim AS builder
ARG NPM_VERSION=10.9.4
RUN npm install -g npm@${NPM_VERSION}

WORKDIR /app/services/frontend

ARG NEXT_PUBLIC_AGENT_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_AGENT_API_URL=${NEXT_PUBLIC_AGENT_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/services/frontend/node_modules ./node_modules
COPY services/frontend ./
COPY services/espresso_mcp ../espresso_mcp
RUN npm run build

FROM node:20-trixie-slim AS runner
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ARG NEXT_PUBLIC_AGENT_API_URL=http://localhost:8000
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_PUBLIC_AGENT_API_URL=${NEXT_PUBLIC_AGENT_API_URL}

WORKDIR /app/services/frontend

COPY --from=builder /app/services/frontend ./
COPY --from=builder /app/services/espresso_mcp ../espresso_mcp

USER 1000:1000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["npm", "run", "start"]
