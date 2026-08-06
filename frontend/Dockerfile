FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Vite bakes VITE_* values into the static bundle at build time, not at
# container runtime — they must be passed as build args, not just env vars
# on the running container. See docker-compose.yml. There is no
# VITE_DATA_MODE — the frontend always reads the live data_mode from the
# backend's own /health response, never a static build-time flag.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
# React Router (BrowserRouter) resolves routes client-side, so nginx must
# fall back to index.html for any path it doesn't have a file for —
# otherwise a direct load or refresh on any route other than "/" 404s.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
