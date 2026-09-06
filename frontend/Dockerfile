FROM node:20-alpine

WORKDIR /app

# Copy package manifests and install dependencies
COPY package.json ./
RUN npm install

# Copy frontend source code
COPY . .

EXPOSE 3000

ENV PORT=3000
ENV REACT_APP_API_URL=http://localhost:8000
ENV WDS_SOCKET_PORT=0

CMD ["npm", "start"]
