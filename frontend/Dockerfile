FROM node:20-alpine AS build
WORKDIR /app

# Copy lockfile + manifest first — Docker caches this layer separately.
# npm ci only re-runs when package-lock.json changes, not on source changes.
COPY package.json package-lock.json ./

# --mount=type=cache speeds up rebuilds by reusing the npm cache across builds.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
