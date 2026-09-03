# -------------------------------------------------------------------
# Stage 1: build
# Installs every dependency, including the dev tooling, and produces
# the static production bundle in /app/dist.
# -------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json ./
RUN npm install

COPY vite.config.js index.html ./
COPY src ./src
RUN npm run build

# -------------------------------------------------------------------
# Stage 2: runtime
# Copies only the built bundle onto Nginx. Node.js, npm, the source
# tree, and node_modules are all left behind in the builder stage.
# -------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
