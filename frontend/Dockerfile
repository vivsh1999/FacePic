# Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Expose port
EXPOSE 4173

# Serve the production build
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0"]
