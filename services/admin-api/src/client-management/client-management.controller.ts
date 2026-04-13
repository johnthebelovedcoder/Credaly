/**
 * Client Management Controller.
 * POST /admin/clients — Create lender client
 * GET /admin/clients — List all clients
 * GET /admin/clients/:id — Get client details
 * POST /admin/clients/:id/suspend — Suspend client
 * POST /admin/clients/:id/terminate — Terminate client
 * POST /admin/clients/:id/rotate-key — Rotate API key
 */
import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Query,
} from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { ClientManagementService, CreateLenderClientDto } from './client-management.service';

@ApiTags('Client Management')
@Controller('admin/clients')
export class ClientManagementController {
  constructor(private readonly clientService: ClientManagementService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new lender client with API key' })
  async createClient(@Body() dto: CreateLenderClientDto) {
    return this.clientService.createClient(dto);
  }

  @Get()
  @ApiOperation({ summary: 'List all lender clients' })
  async listClients(@Query('status') status?: string) {
    return this.clientService.listClients(status);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get lender client details' })
  async getClient(@Param('id') id: string) {
    return this.clientService.getClientById(id);
  }

  @Post(':id/suspend')
  @ApiOperation({ summary: 'Suspend a lender client' })
  async suspendClient(@Param('id') id: string) {
    return this.clientService.suspendClient(id);
  }

  @Post(':id/terminate')
  @ApiOperation({ summary: 'Terminate a lender client' })
  async terminateClient(@Param('id') id: string) {
    return this.clientService.terminateClient(id);
  }

  @Post(':id/reactivate')
  @ApiOperation({ summary: 'Reactivate a suspended lender client' })
  async reactivateClient(@Param('id') id: string) {
    return this.clientService.reactivateClient(id);
  }

  @Post(':id/rotate-key')
  @ApiOperation({ summary: 'Rotate API key for a lender client' })
  async rotateKey(@Param('id') id: string) {
    return this.clientService.rotateApiKey(id);
  }
}
