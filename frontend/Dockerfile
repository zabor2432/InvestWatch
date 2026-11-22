FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Obraz używa prawdziwego backendu (/api, /ws/alerts). Mocki tylko w `npm run dev` (.env.development).
ARG VITE_USE_MOCKS=false
ARG VITE_API_URL=/api
ARG VITE_WS_URL=
ENV VITE_USE_MOCKS=$VITE_USE_MOCKS VITE_API_URL=$VITE_API_URL VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
