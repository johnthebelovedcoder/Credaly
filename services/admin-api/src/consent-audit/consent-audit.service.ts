/**
 * Consent Audit Service — PRD FR-041, US-019.
 * Searchable consent audit log by BVN hash, date range, event type.
 */
import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Between } from 'typeorm';
import { ConsentAuditEntity } from './consent-audit.entity';

@Injectable()
export class ConsentAuditService {
  constructor(
    @InjectRepository(ConsentAuditEntity)
    private readonly auditRepo: Repository<ConsentAuditEntity>,
  ) {}

  /**
   * Query consent audit log with filters. PRD FR-041.
   * Searchable by BVN hash (via consent join), date range, and event type.
   */
  async queryAuditLog(params: {
    consentId?: string;
    eventType?: string;
    startDate?: Date;
    endDate?: Date;
    limit?: number;
    offset?: number;
  }): Promise<{ entries: ConsentAuditEntity[]; total: number }> {
    const qb = this.auditRepo.createQueryBuilder('audit');

    if (params.consentId) {
      qb.andWhere('audit.consent_id = :consentId', { consentId: params.consentId });
    }
    if (params.eventType) {
      qb.andWhere('audit.event_type = :eventType', { eventType: params.eventType });
    }
    if (params.startDate && params.endDate) {
      qb.andWhere('audit.timestamp BETWEEN :start AND :end', {
        start: params.startDate,
        end: params.endDate,
      });
    }

    const [entries, total] = await qb
      .orderBy('audit.timestamp', 'DESC')
      .take(params.limit || 50)
      .skip(params.offset || 0)
      .getManyAndCount();

    return { entries, total };
  }

  /**
   * Verify tamper-evidence of audit log chain.
   * Checks that each row's previous_row_hash matches the preceding row's row_hash.
   */
  async verifyIntegrity(consentId: string): Promise<{
    isValid: boolean;
    firstInvalidEntry?: number;
    totalEntries: number;
  }> {
    const entries = await this.auditRepo.find({
      where: { consentId },
      order: { id: 'ASC' },
    });

    if (entries.length <= 1) {
      return { isValid: true, totalEntries: entries.length };
    }

    for (let i = 1; i < entries.length; i++) {
      if (entries[i].previousRowHash !== entries[i - 1].rowHash) {
        return {
          isValid: false,
          firstInvalidEntry: entries[i].id,
          totalEntries: entries.length,
        };
      }
    }

    return { isValid: true, totalEntries: entries.length };
  }
}
