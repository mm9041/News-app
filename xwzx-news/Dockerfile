FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# 空串表示走相对路径：请求 /api/* 由 nginx 反代到 backend:8000，避免 CORS
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
