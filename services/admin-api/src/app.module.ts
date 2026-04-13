/**
 * Root AppModule — imports all feature modules.
 * AuthModule is global — provides JWT strategy for all protected routes.
 */
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { ScheduleModule } from '@nestjs/schedule';

// Feature modules
import { PipelineModule } from './pipeline/pipeline.module';
import { ModelMetricsModule } from './model-metrics/model-metrics.module';
import { ClientManagementModule } from './client-management/client-management.module';
import { ConsentAuditModule } from './consent-audit/consent-audit.module';
import { HealthModule } from './health/health.module';
import { UsageModule } from './usage/usage.module';

// Previously orphaned modules — now wired in
import { ApiKeyModule } from './api-key-mgmt/api-key.module';
import { WebhookModule } from './webhook/webhook.module';

// Auth — must be imported to register JWT strategy
import { AuthModule } from './auth/auth.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        type: configService.get<string>('DB_TYPE', 'better-sqlite3') as any,
        database: configService.get<string>('DB_DATABASE', './credaly.db'),
        // For PostgreSQL in production:
        // type: 'postgres',
        // host: configService.get<string>('DB_HOST', 'localhost'),
        // port: configService.get<number>('DB_PORT', 5432),
        // username: configService.get<string>('DB_USERNAME'),
        // password: configService.get<string>('DB_PASSWORD'),
        // database: configService.get<string>('DB_NAME', 'credaly'),
        entities: [__dirname + '/**/*.entity{.ts,.js}'],
        // IMPORTANT: synchronize disabled — SQLAlchemy (scoring API) owns the schema.
        // NestJS reads only. Run `alembic upgrade head` to create/update tables.
        synchronize: false,
        logging: configService.get<string>('NODE_ENV') === 'development',
      }),
      inject: [ConfigService],
    }),
    ScheduleModule.forRoot(),

    // Auth module (registers JWT strategy globally)
    AuthModule,

    // Feature modules
    PipelineModule,
    ModelMetricsModule,
    ClientManagementModule,
    ConsentAuditModule,
    HealthModule,
    UsageModule,

    // Previously orphaned — now wired in
    ApiKeyModule,
    WebhookModule,
  ],
})
export class AppModule {}
