/**
 * Consent Audit Controller.
 * GET /admin/consent — Query audit log
 * GET /admin/consent/verify/:consentId — Verify tamper-evidence integrity
 */
import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { ConsentAuditService } from './consent-audit.service';

@ApiTags('Consent Audit')
@Controller('admin/consent')
export class ConsentAuditController {
  constructor(private readonly auditService: ConsentAuditService) {}

  @Get()
  @ApiOperation({ summary: 'Query consent audit log' })
  async queryAuditLog(
    @Query('consent_id') consentId?: string,
    @Query('event_type') eventType?: string,
    @Query('start_date') startDate?: string,
    @Query('end_date') endDate?: string,
    @Query('limit') limit?: number,
    @Query('offset') offset?: number,
  ) {
    return this.auditService.queryAuditLog({
      consentId,
      eventType,
      startDate: startDate ? new Date(startDate) : undefined,
      endDate: endDate ? new Date(endDate) : undefined,
      limit: limit ? parseInt(String(limit)) : 50,
      offset: offset ? parseInt(String(offset)) : 0,
    });
  }

  @Get('verify/:consentId')
  @ApiOperation({ summary: 'Verify tamper-evidence integrity of audit log chain' })
  async verifyIntegrity(@Param('consentId') consentId: string) {
    return this.auditService.verifyIntegrity(consentId);
  }
}
