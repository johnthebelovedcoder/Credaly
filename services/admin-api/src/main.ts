/**
 * NestJS Admin API — Main entry point.
 * Per PRD FR-038 through FR-042: admin dashboard backend.
 */
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import helmet from 'helmet';
import * as jwt from 'jsonwebtoken';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // ── Security headers ──────────────────────────────────────────────
  app.use(
    helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          scriptSrc: ["'self'", "'unsafe-inline'"], // Required for Swagger
          styleSrc: ["'self'", "'unsafe-inline'"], // Required for Swagger
        },
      },
      hsts: {
        maxAge: 31536000, // 1 year
        includeSubDomains: true,
        preload: true,
      },
    }),
  );

  // ── CORS ──────────────────────────────────────────────────────────
  const allowedOrigins = process.env.ADMIN_FRONTEND_URL
    ? process.env.ADMIN_FRONTEND_URL.split(',')
    : ['http://localhost:3000'];

  app.enableCors({
    origin: (origin, callback) => {
      // Allow requests with no origin (e.g., curl, Postman, mobile apps)
      if (!origin || allowedOrigins.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error('Not allowed by CORS'));
      }
    },
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID'],
    exposedHeaders: ['X-Request-ID'],
  });

  // ── Global validation pipe ────────────────────────────────────────
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: {
        enableImplicitConversion: true,
      },
      disableErrorMessages: process.env.NODE_ENV === 'production',
    }),
  );

  // ── Request ID middleware ──────────────────────────────────────────
  app.use((req, res, next) => {
    if (!req.headers['x-request-id']) {
      req.headers['x-request-id'] = `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    }
    res.setHeader('X-Request-ID', req.headers['x-request-id'] as string);
    next();
  });

  // ── Rate limiting (basic in-memory — replace with Redis in prod) ──
  const rateLimitStore = new Map<string, { count: number; resetAt: number }>();
  const RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute
  const RATE_LIMIT_MAX = process.env.ADMIN_RATE_LIMIT_PER_MINUTE
    ? parseInt(process.env.ADMIN_RATE_LIMIT_PER_MINUTE, 10)
    : 100;

  app.use((req, res, next) => {
    if (req.path === '/admin/health' || req.path === '/api/docs' || req.path.startsWith('/api/docs/')) {
      return next(); // Don't rate limit health or docs
    }

    const ip = req.ip || req.socket.remoteAddress || 'unknown';
    const now = Date.now();
    const entry = rateLimitStore.get(ip);

    if (!entry || now > entry.resetAt) {
      rateLimitStore.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
      return next();
    }

    entry.count += 1;
    if (entry.count > RATE_LIMIT_MAX) {
      res.setHeader('Retry-After', Math.ceil((entry.resetAt - now) / 1000).toString());
      return res.status(429).json({
        statusCode: 429,
        message: 'Too many requests — rate limit exceeded',
        error: 'Too Many Requests',
      });
    }

    next();
  });

  // ── Swagger / OpenAPI docs ────────────────────────────────────────
  const config = new DocumentBuilder()
    .setTitle('Credaly Admin API')
    .setDescription(
      'Admin dashboard backend — model monitoring, pipeline health, client management, consent audit',
    )
    .setVersion('1.0')
    .addBearerAuth(
      {
        type: 'http',
        scheme: 'bearer',
        bearerFormat: 'JWT',
        name: 'JWT',
        description: 'Enter JWT access token',
        in: 'header',
      },
      'bearerAuth',
    )
    .addTag('auth', 'Authentication and admin user management')
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document, {
    swaggerOptions: {
      persistAuthorization: true,
    },
  });

  // ── Graceful shutdown ─────────────────────────────────────────────
  const gracefulShutdown = async (signal: string) => {
    console.log(`${signal} received — shutting down gracefully`);
    await app.close();
    process.exit(0);
  };

  process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
  process.on('SIGINT', () => gracefulShutdown('SIGINT'));

  // ── Start server ──────────────────────────────────────────────────
  const port = process.env.ADMIN_API_PORT || 3001;
  await app.listen(port);
  console.log(`Admin API running on http://localhost:${port}`);
  console.log(`Swagger docs at http://localhost:${port}/api/docs`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
}

bootstrap();
