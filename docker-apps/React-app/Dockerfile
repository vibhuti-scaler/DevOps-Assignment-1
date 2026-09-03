# Build stage: install dependencies and produce the static bundle.
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY vite.config.js index.html ./
COPY src ./src
RUN npm run build

# Runtime stage: serve only the built files with Nginx.
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
