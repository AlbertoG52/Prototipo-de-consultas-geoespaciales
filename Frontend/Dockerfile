FROM node:24-slim

WORKDIR /app

COPY package*.json ./
# Sin package-lock.json se usa "npm install"; con él, conviene "npm ci" para builds
# reproducibles.
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
