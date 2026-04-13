/**
 * Webhook Management Controller.
 * GET /v1/webhooks — List all webhooks
 * POST /v1/webhooks — Create webhook
 * DELETE /v1/webhooks/:id — Delete webhook
 * POST /v1/webhooks/:id/test — Test webhook
 * GET /v1/webhooks/:id/deliveries — Get webhook deliveries
 * POST /v1/webhooks/deliveries/:id/replay — Replay webhook delivery
 */
import { Controller, Get, Post, Delete, Body, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { WebhookService, CreateWebhookDto } from './webhook.service';

@ApiTags('Webhook Management')
@Controller('v1/webhooks')
export class WebhookController {
  constructor(private readonly webhookService: WebhookService) {}

  @Get()
  @ApiOperation({ summary: 'List all webhook subscriptions' })
  async getWebhooks(@Query('clientId') clientId?: string) {
    return this.webhookService.getWebhooks(clientId);
  }

  @Post()
  @ApiOperation({ summary: 'Create a new webhook subscription' })
  async createWebhook(@Body() dto: CreateWebhookDto) {
    return this.webhookService.createWebhook(dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete a webhook subscription' })
  async deleteWebhook(@Param('id') id: string) {
    return this.webhookService.deleteWebhook(id);
  }

  @Post(':id/test')
  @ApiOperation({ summary: 'Test a webhook by sending a ping event' })
  async testWebhook(@Param('id') id: string) {
    return this.webhookService.testWebhook(id);
  }

  @Get(':id/deliveries')
  @ApiOperation({ summary: 'Get webhook delivery history' })
  async getWebhookDeliveries(@Param('id') id: string) {
    return this.webhookService.getWebhookDeliveries(id);
  }

  @Post('deliveries/:id/replay')
  @ApiOperation({ summary: 'Replay a failed webhook delivery' })
  async replayWebhook(@Param('id') id: string) {
    return this.webhookService.replayWebhook(id);
  }
}
