FROM oven/bun:1

WORKDIR /app

COPY package.json ./
COPY package-lock.json ./

RUN bun install --production

COPY src ./src

ENV PORT=8080
EXPOSE 8080

CMD ["bun", "src/index.ts"]
