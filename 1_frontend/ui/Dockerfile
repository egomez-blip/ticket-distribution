# Stage 1: build (transpila TS y empaqueta)
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npx ui5 build --clean-dest && cp dist/index-cdn.html dist/index.html

# Stage 2: servir estático con nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
