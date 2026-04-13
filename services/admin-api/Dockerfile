# NestJS Admin API Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install system dependencies for better-sqlite3
RUN apk add --no-cache python3 make g++

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Build TypeScript
RUN npm run build

# Expose port
EXPOSE 3001

# Default command
CMD ["npm", "run", "start:prod"]
