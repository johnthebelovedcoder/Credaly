/**
 * Health Check Controller.
 */
import { Controller, Get } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';

@ApiTags('Health')
@Controller('admin/health')
export class HealthController {
  @Get()
  @ApiOperation({ summary: 'Health check' })
  async health() {
    return {
      status: 'ok',
      service: 'Credaly Admin API',
      timestamp: new Date().toISOString(),
    };
  }
}
