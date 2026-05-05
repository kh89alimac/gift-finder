# --- Dependencies -----------------------------------------------------------------

FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* yarn.lock* ./
RUN npm ci --only=production


# --- Builder -----------------------------------------------------------------------

FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* yarn.lock* ./
RUN npm ci

COPY . .
RUN npm run build


# --- Runner -----------------------------------------------------------------------

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Non-root user for security
RUN addgroup --gid 1001 -S nodejs
RUN adduser --uid 1001 -S nextjs -G nodejs

# Copy public assets and .next/standalone from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -O- http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
