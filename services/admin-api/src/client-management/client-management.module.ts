/**
 * Client Management Module — PRD FR-040, US-007, US-009.
 * CRUD for lender clients: create, suspend, terminate, view usage.
 */
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { LenderClientEntity } from './lender-client.entity';
import { ClientManagementController } from './client-management.controller';
import { ClientManagementService } from './client-management.service';

@Module({
  imports: [TypeOrmModule.forFeature([LenderClientEntity])],
  controllers: [ClientManagementController],
  providers: [ClientManagementService],
  exports: [ClientManagementService],
})
export class ClientManagementModule {}
