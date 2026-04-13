/**
 * Consent Audit Module — PRD FR-041, FR-019, US-019.
 * GET /admin/consent — consent audit log viewer.
 */
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConsentAuditEntity } from './consent-audit.entity';
import { ConsentAuditController } from './consent-audit.controller';
import { ConsentAuditService } from './consent-audit.service';

@Module({
  imports: [TypeOrmModule.forFeature([ConsentAuditEntity])],
  controllers: [ConsentAuditController],
  providers: [ConsentAuditService],
  exports: [ConsentAuditService],
})
export class ConsentAuditModule {}
