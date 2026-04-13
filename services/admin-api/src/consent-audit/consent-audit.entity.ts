/**
 * Consent Audit Log Entity — mirrors consent_audit_log table.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn } from 'typeorm';

@Entity('consent_audit_log')
export class ConsentAuditEntity {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'consent_id' })
  consentId: string;

  @Column({ name: 'event_type' })
  eventType: string;

  @Column({ name: 'timestamp', type: 'datetime' })
  timestamp: Date;

  @Column({ name: 'ip_address', nullable: true })
  ipAddress: string;

  @Column({ name: 'user_agent', nullable: true })
  userAgent: string;

  @Column({ name: 'actor_id', nullable: true })
  actorId: string;

  @Column({ name: 'previous_row_hash' })
  previousRowHash: string;

  @Column({ name: 'row_hash' })
  rowHash: string;
}
