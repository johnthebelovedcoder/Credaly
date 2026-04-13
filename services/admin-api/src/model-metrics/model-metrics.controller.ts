/**
 * Model Metrics Controller.
 */
import { Controller, Get, Post } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { ModelMetricsService, ModelMetrics } from './model-metrics.service';

@ApiTags('Model Metrics')
@Controller('admin/metrics')
export class ModelMetricsController {
  constructor(private readonly metricsService: ModelMetricsService) {}

  @Get()
  @ApiOperation({ summary: 'Get current model performance metrics' })
  async getMetrics(): Promise<ModelMetrics> {
    return this.metricsService.getModelMetrics();
  }

  @Get('psi-alerts')
  @ApiOperation({ summary: 'Get PSI drift alerts' })
  async getPsiAlerts() {
    return this.metricsService.getPsiAlerts();
  }

  @Get('score-distribution')
  @ApiOperation({ summary: 'Get score distribution histogram' })
  async getScoreDistribution() {
    return this.metricsService.getScoreDistribution();
  }

  @Post('retrain')
  @ApiOperation({ summary: 'Trigger manual model retraining' })
  async triggerRetraining() {
    return this.metricsService.triggerRetraining();
  }
}
