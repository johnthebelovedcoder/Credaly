/**
 * Lender Usage Controller.
 * GET /admin/clients/:id/usage — view API usage, spending, rate limit headroom.
 */
import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { UsageService } from './usage.service';

@ApiTags('Lender Usage')
@Controller('admin/clients/:clientId/usage')
export class UsageController {
  constructor(private readonly usageService: UsageService) {}

  @Get()
  @ApiOperation({ summary: 'Get API usage statistics for a lender' })
  async getUsage(
    @Param('clientId') clientId: string,
    @Query('days') days: number = 30,
  ) {
    return this.usageService.getUsage(clientId, parseInt(String(days)));
  }

  @Get('rate-limit')
  @ApiOperation({ summary: 'Get rate limit headroom for a lender' })
  async getRateLimitHeadroom(
    @Param('clientId') clientId: string,
    @Query('limit') limit: number = 100,
  ) {
    return this.usageService.getRateLimitHeadroom(clientId, parseInt(String(limit)));
  }
}
