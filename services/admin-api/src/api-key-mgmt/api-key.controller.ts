/**
 * API Key Management Controller.
 * GET /v1/api-keys — List all API keys
 * POST /v1/api-keys — Create API key
 * POST /v1/api-keys/:id/rotate — Rotate API key
 * DELETE /v1/api-keys/:id — Revoke API key
 */
import { Controller, Get, Post, Delete, Body, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { ApiKeyService, CreateApiKeyDto, RotateApiKeyDto } from './api-key.service';

@ApiTags('API Key Management')
@Controller('v1/api-keys')
export class ApiKeyController {
  constructor(private readonly apiKeyService: ApiKeyService) {}

  @Get()
  @ApiOperation({ summary: 'List all API keys' })
  async getApiKeys(@Query('clientId') clientId?: string) {
    return this.apiKeyService.getApiKeys(clientId);
  }

  @Post()
  @ApiOperation({ summary: 'Create a new API key' })
  async createApiKey(@Body() dto: CreateApiKeyDto) {
    return this.apiKeyService.createApiKey(dto);
  }

  @Post(':id/rotate')
  @ApiOperation({ summary: 'Rotate an API key (revoke old, create new)' })
  async rotateApiKey(
    @Param('id') id: string,
    @Body() dto?: RotateApiKeyDto,
  ) {
    return this.apiKeyService.rotateApiKey(id, dto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Revoke an API key' })
  async revokeApiKey(@Param('id') id: string, @Query('revokedBy') revokedBy?: string) {
    return this.apiKeyService.revokeApiKey(id, revokedBy);
  }
}
