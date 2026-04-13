/**
 * Consent Audit Log Entity — mirrors consent_audit_log table.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn } from 'typeorm';

@Entity('consent_audit_log')
export class ConsentAuditEntity {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'consent_id', type: 'varchar', length: 36 })
  consentId: string;

  @Column({ name: 'event_type', type: 'varchar', length: 50 })
  eventType: string;

  @Column({ name: 'timestamp', type: 'datetime' })
  timestamp: Date;

  @Column({ name: 'ip_address', type: 'varchar', length: 45, nullable: true })
  ipAddress: string;

  @Column({ name: 'user_agent', type: 'varchar', length: 500, nullable: true })
  userAgent: string;

  @Column({ name: 'actor_id', type: 'varchar', length: 36, nullable: true })
  actorId: string;

  @Column({ name: 'previous_row_hash' })
  previousRowHash: string;

  @Column({ name: 'row_hash' })
  rowHash: string;
}
