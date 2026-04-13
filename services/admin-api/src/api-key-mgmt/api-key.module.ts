/**
 * API Key Management Module.
 */
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ApiKeyEntity } from './api-key.entity';
import { ApiKeyController } from './api-key.controller';
import { ApiKeyService } from './api-key.service';

@Module({
  imports: [TypeOrmModule.forFeature([ApiKeyEntity])],
  controllers: [ApiKeyController],
  providers: [ApiKeyService],
  exports: [ApiKeyService],
})
export class ApiKeyModule {}
