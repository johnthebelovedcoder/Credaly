/**
 * End-to-End Tests — Admin API
 * Tests the full request-response cycle with a real (in-memory) database.
 */
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppModule } from '../src/app.module';
import { AdminUserEntity } from '../src/auth/admin-user.entity';
import * as bcrypt from 'bcrypt';

describe('Admin API (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [
        TypeOrmModule.forRoot({
          type: 'better-sqlite3',
          database: ':memory:',
          entities: [AdminUserEntity],
          synchronize: true,
          logging: false,
        }),
        AppModule,
      ],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  // ── Health Endpoint ──────────────────────────────────────────────────

  describe('GET /admin/health', () => {
    it('should return healthy', () => {
      return request(app.getHttpServer())
        .get('/admin/health')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('status');
        });
    });
  });

  // ── Auth Endpoints ──────────────────────────────────────────────────

  describe('POST /admin/auth/login', () => {
    it('should reject missing credentials', () => {
      return request(app.getHttpServer())
        .post('/admin/auth/login')
        .send({})
        .expect(401);
    });

    it('should reject invalid credentials', () => {
      return request(app.getHttpServer())
        .post('/admin/auth/login')
        .send({ email: 'nonexistent@credaly.io', password: 'wrong' })
        .expect(401);
    });
  });

  // ── Pipeline Health ────────────────────────────────────────────────

  describe('GET /admin/pipeline/health', () => {
    it('should return pipeline status', () => {
      return request(app.getHttpServer())
        .get('/admin/pipeline/health')
        .expect(200);
    });
  });

  // ── Consent Audit ──────────────────────────────────────────────────

  describe('GET /admin/consent', () => {
    it('should return consent audit log (empty)', () => {
      return request(app.getHttpServer())
        .get('/admin/consent')
        .expect(200)
        .expect((res) => {
          expect(Array.isArray(res.body) || res.body.items).toBeTruthy();
        });
    });
  });

  // ── Model Metrics ──────────────────────────────────────────────────

  describe('GET /admin/metrics', () => {
    it('should return model metrics (placeholder)', () => {
      return request(app.getHttpServer())
        .get('/admin/metrics')
        .expect(200)
        .expect((res) => {
          expect(res.body).toHaveProperty('model_version');
        });
    });
  });
});
