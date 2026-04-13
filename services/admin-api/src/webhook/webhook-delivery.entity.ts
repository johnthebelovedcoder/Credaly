/**
 * Webhook Delivery Entity — tracks webhook delivery attempts.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn } from 'typeorm';

@Entity('webhook_delivery')
export class WebhookDeliveryEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'subscription_id' })
  subscriptionId: string;

  @Column({ name: 'event_type' })
  eventType: string;

  @Column({ name: 'payload', type: 'text' }) // JSON payload
  payload: string;

  @Column({ name: 'response_status', nullable: true })
  responseStatus: number;

  @Column({ name: 'response_body', type: 'text', nullable: true })
  responseBody: string;

  @Column({ default: false })
  success: boolean;

  @Column({ name: 'attempt_count', default: 1 })
  attemptCount: number;

  @Column({ name: 'next_retry_at', type: 'datetime', nullable: true })
  nextRetryAt: Date;

  @Column({ name: 'replayed', default: false })
  replayed: boolean;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
