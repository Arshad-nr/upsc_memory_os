# ── Stage 1: Dependencies ────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: Build ───────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env vars for Next.js (public vars must be set at build time)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ── Stage 3: Runtime ─────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

# Install wget for health checks and create non-root user
RUN apk add --no-cache wget && \
    addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
