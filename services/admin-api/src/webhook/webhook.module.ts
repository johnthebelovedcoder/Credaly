/**
 * Webhook Management Module.
 */
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { WebhookSubscriptionEntity } from './webhook-subscription.entity';
import { WebhookDeliveryEntity } from './webhook-delivery.entity';
import { WebhookController } from './webhook.controller';
import { WebhookService } from './webhook.service';

@Module({
  imports: [TypeOrmModule.forFeature([WebhookSubscriptionEntity, WebhookDeliveryEntity])],
  controllers: [WebhookController],
  providers: [WebhookService],
  exports: [WebhookService],
})
export class WebhookModule {}
