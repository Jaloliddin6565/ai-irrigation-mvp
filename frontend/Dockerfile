FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Vite bakes VITE_* values into the static bundle at build time, not at
# container runtime — they must be passed as build args, not just env vars
# on the running container. See docker-compose.yml.
ARG VITE_API_BASE_URL
ARG VITE_DATA_MODE
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_DATA_MODE=${VITE_DATA_MODE}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
