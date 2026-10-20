# Frontend de producción: se compila una vez y Caddy sirve los archivos.
# El contexto de construcción es ../Frontend (ver docker-compose.prod.yml).

# --- 1. Compilar (tsc + vite build) ---
FROM node:24-slim AS compilar
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Dirección del backend vista desde el navegador: "/api" en el mismo dominio.
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- 2. Servir con Caddy (el Caddyfile se monta desde despliegue/) ---
FROM caddy:2.8.4-alpine
COPY --from=compilar /app/dist /srv
