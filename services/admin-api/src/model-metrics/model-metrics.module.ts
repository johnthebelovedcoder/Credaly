/**
 * Model Metrics Module — PRD FR-039, US-016.
 * GET /admin/metrics — Gini coefficient, PSI, KS statistic, score distribution.
 */
import { Module } from '@nestjs/common';
import { ModelMetricsController } from './model-metrics.controller';
import { ModelMetricsService } from './model-metrics.service';

@Module({
  controllers: [ModelMetricsController],
  providers: [ModelMetricsService],
  exports: [ModelMetricsService],
})
export class ModelMetricsModule {}
