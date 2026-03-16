# ── Stage 1: Build ──────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm pkg delete scripts.postinstall && npm ci
COPY . .
RUN npx nuxt prepare && npm run build

# ── Stage 2: Runtime ────────────────────────────────────
FROM node:22-alpine

WORKDIR /app
COPY --from=builder /app/.output .output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
