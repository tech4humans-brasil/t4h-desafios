FROM node:20.18.0-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY src ./src

ENV NODE_ENV=production \
    TZ=UTC

EXPOSE 3000

CMD ["node", "src/server.js"]
