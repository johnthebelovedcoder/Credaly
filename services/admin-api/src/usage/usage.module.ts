/**
 * Lender Usage Tracking Module — US-009.
 * GET /admin/clients/:id/usage — view API usage, spending, rate limit headroom.
 */
import { Module } from '@nestjs/common';
import { RedisModule } from '../redis/redis.module';
import { UsageController } from './usage.controller';
import { UsageService } from './usage.service';

@Module({
  imports: [RedisModule],
  controllers: [UsageController],
  providers: [UsageService],
  exports: [UsageService],
})
export class UsageModule {}
