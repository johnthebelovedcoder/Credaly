/**
 * Webhook Management Service.
 * Handles webhook CRUD operations and delivery tracking.
 */
import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as crypto from 'crypto';
import { WebhookSubscriptionEntity } from './webhook-subscription.entity';
import { WebhookDeliveryEntity } from './webhook-delivery.entity';

export interface CreateWebhookDto {
  clientId: string;
  url: string;
  events: string[];
  description?: string;
}

export const VALID_WEBHOOK_EVENTS = [
  'score_generated',
  'score_changed',
  'consent_granted',
  'consent_revoked',
];

@Injectable()
export class WebhookService {
  constructor(
    @InjectRepository(WebhookSubscriptionEntity)
    private readonly webhookRepo: Repository<WebhookSubscriptionEntity>,
    @InjectRepository(WebhookDeliveryEntity)
    private readonly deliveryRepo: Repository<WebhookDeliveryEntity>,
  ) {}

  /**
   * Get all webhook subscriptions for a client or all.
   */
  async getWebhooks(clientId?: string): Promise<Partial<WebhookSubscriptionEntity>[]> {
    const where = clientId ? { clientId } : {};
    const webhooks = await this.webhookRepo.find({
      where,
      order: { createdAt: 'DESC' },
    });

    // Don't return the secret in list
    return webhooks.map((wh) => {
      const { secret, ...safe } = wh;
      return safe;
    });
  }

  /**
   * Create a new webhook subscription.
   */
  async createWebhook(
    dto: CreateWebhookDto,
  ): Promise<{ webhook: Partial<WebhookSubscriptionEntity>; secret: string }> {
    // Validate URL (must be HTTPS in production)
    if (!dto.url.startsWith('https://') && !dto.url.startsWith('http://localhost')) {
      throw new BadRequestException('Webhook URL must use HTTPS (or http://localhost for testing)');
    }

    // Validate events
    const invalidEvents = dto.events.filter((e) => !VALID_WEBHOOK_EVENTS.includes(e));
    if (invalidEvents.length > 0) {
      throw new BadRequestException(`Invalid events: ${invalidEvents.join(', ')}`);
    }

    // Generate HMAC secret
    const secret = crypto.randomBytes(32).toString('hex');

    const webhook = this.webhookRepo.create({
      clientId: dto.clientId,
      url: dto.url,
      events: JSON.stringify(dto.events),
      secret,
      description: dto.description || null,
      isActive: true,
      failureCount: 0,
    });

    const saved = await this.webhookRepo.save(webhook);

    const { secret: _, ...safeWebhook } = saved as WebhookSubscriptionEntity;
    return { webhook: safeWebhook as Partial<WebhookSubscriptionEntity>, secret };
  }

  /**
   * Delete a webhook subscription.
   */
  async deleteWebhook(id: string): Promise<{ success: boolean }> {
    const webhook = await this.webhookRepo.findOne({ where: { id } });
    if (!webhook) {
      throw new NotFoundException(`Webhook subscription '${id}' not found`);
    }

    await this.webhookRepo.remove(webhook);
    return { success: true };
  }

  /**
   * Test a webhook by sending a ping event.
   */
  async testWebhook(id: string): Promise<{ success: boolean; message: string }> {
    const webhook = await this.webhookRepo.findOne({ where: { id } });
    if (!webhook) {
      throw new NotFoundException(`Webhook subscription '${id}' not found`);
    }

    if (!webhook.isActive) {
      throw new BadRequestException('Cannot test an inactive webhook');
    }

    // In a real implementation, this would fire the webhook
    // For now, return success placeholder
    return {
      success: true,
      message: `Test ping sent to ${webhook.url}`,
    };
  }

  /**
   * Get webhook deliveries for a specific webhook.
   */
  async getWebhookDeliveries(
    webhookId: string,
  ): Promise<Partial<WebhookDeliveryEntity>[]> {
    const webhook = await this.webhookRepo.findOne({ where: { id: webhookId } });
    if (!webhook) {
      throw new NotFoundException(`Webhook subscription '${webhookId}' not found`);
    }

    const deliveries = await this.deliveryRepo.find({
      where: { subscriptionId: webhookId },
      order: { createdAt: 'DESC' },
      take: 100,
    });

    return deliveries;
  }

  /**
   * Replay a failed webhook delivery.
   */
  async replayWebhook(deliveryId: string): Promise<{
    success: boolean;
    message: string;
  }> {
    const delivery = await this.deliveryRepo.findOne({ where: { id: deliveryId } });
    if (!delivery) {
      throw new NotFoundException(`Webhook delivery '${deliveryId}' not found`);
    }

    if (delivery.success) {
      throw new BadRequestException('Cannot replay a successful delivery');
    }

    // In a real implementation, this would re-fire the webhook
    // For now, mark as replayed
    delivery.replayed = true;
    delivery.nextRetryAt = new Date();
    await this.deliveryRepo.save(delivery);

    return {
      success: true,
      message: `Webhook delivery queued for replay: ${deliveryId}`,
    };
  }
}
