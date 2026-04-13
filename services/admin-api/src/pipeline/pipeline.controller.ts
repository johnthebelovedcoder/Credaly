/**
 * Pipeline Health Controller.
 * GET /admin/pipeline/health
 * GET /admin/pipeline/:source/history
 */
import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { PipelineService } from './pipeline.service';

@ApiTags('Pipeline Health')
@Controller('admin/pipeline')
export class PipelineController {
  constructor(private readonly pipelineService: PipelineService) {}

  @Get('health')
  @ApiOperation({ summary: 'Get current pipeline health for all data sources' })
  @ApiResponse({ status: 200, description: 'Pipeline health status' })
  async getHealth() {
    return this.pipelineService.getPipelineHealth();
  }

  @Get(':source/history')
  @ApiOperation({ summary: 'Get historical pipeline runs for a source' })
  async getHistory(
    @Param('source') source: string,
    @Query('limit') limit: number = 20,
    @Query('offset') offset: number = 0,
  ) {
    return this.pipelineService.getSourceHistory(source, limit, offset);
  }

  @Get('uptime')
  @ApiOperation({ summary: 'Get pipeline uptime percentage' })
  async getUptime(@Query('hours') hours: number = 24) {
    return this.pipelineService.getPipelineUptime(hours);
  }
}
