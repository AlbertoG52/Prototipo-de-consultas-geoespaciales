FROM node:24-slim

WORKDIR /app

COPY package*.json ./
# En el primer arranque no hay package-lock.json; luego cambiá a "npm ci" para builds reproducibles
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
