/**
 * Webhook Subscription Entity.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';

@Entity('webhook_subscription')
export class WebhookSubscriptionEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'client_id', type: 'varchar', length: 36 })
  clientId: string;

  @Column({ name: 'url', type: 'varchar', length: 500 })
  url: string;

  @Column({ name: 'events', type: 'text' }) // JSON array
  events: string;

  @Column({ name: 'secret', type: 'varchar', length: 128, nullable: true })
  secret: string | null; // HMAC secret for signature

  @Column({ name: 'description', type: 'varchar', length: 500, nullable: true })
  description: string | null;

  @Column({ default: true })
  isActive: boolean;

  @Column({ name: 'last_triggered_at', type: 'datetime', nullable: true })
  lastTriggeredAt: Date;

  @Column({ name: 'failure_count', default: 0 })
  failureCount: number;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
