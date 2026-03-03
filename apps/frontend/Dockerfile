# ── Stage 1: Build ──────────────────────────────────────
FROM node:25-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# ── Stage 2: Runtime ────────────────────────────────────
FROM node:25-alpine

WORKDIR /app
COPY --from=builder /app/.output .output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
