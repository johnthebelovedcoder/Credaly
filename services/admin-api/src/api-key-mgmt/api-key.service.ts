/**
 * API Key Management Service.
 * Handles API key CRUD operations for clients.
 */
import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import { ApiKeyEntity } from './api-key.entity';

export interface CreateApiKeyDto {
  clientId: string;
  keyName?: string;
  ipAllowlist?: string[];
  expiresAt?: string;
}

export interface RotateApiKeyDto {
  ipAllowlist?: string[];
}

@Injectable()
export class ApiKeyService {
  constructor(
    @InjectRepository(ApiKeyEntity)
    private readonly apiKeyRepo: Repository<ApiKeyEntity>,
  ) {}

  /**
   * Get all API keys for a client or all keys.
   */
  async getApiKeys(clientId?: string): Promise<Partial<ApiKeyEntity>[]> {
    const where = clientId ? { clientId } : {};
    const keys = await this.apiKeyRepo.find({
      where,
      order: { createdAt: 'DESC' },
    });

    // Never return the hash, only metadata
    return keys.map((key) => ({
      id: key.id,
      clientId: key.clientId,
      keyPrefix: key.keyPrefix,
      keyName: key.keyName,
      isActive: key.isActive,
      lastUsedAt: key.lastUsedAt,
      expiresAt: key.expiresAt,
      revokedAt: key.revokedAt,
      revokedBy: key.revokedBy,
      ipAllowlist: key.ipAllowlist,
      createdAt: key.createdAt,
      updatedAt: key.updatedAt,
    }));
  }

  /**
   * Create a new API key for a client.
   */
  async createApiKey(dto: CreateApiKeyDto): Promise<{
    apiKey: Partial<ApiKeyEntity>;
    rawKey: string;
  }> {
    // Generate API key
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2);
    const rawKey = `credaly_${timestamp}_${random}`;

    // Hash with bcrypt
    const saltRounds = 12;
    const hashedKey = await bcrypt.hash(rawKey, saltRounds);

    // Store prefix for identification
    const keyPrefix = rawKey.substring(0, 20);

    const apiKey: ApiKeyEntity = Object.assign(new ApiKeyEntity(), {
      clientId: dto.clientId,
      keyHash: hashedKey,
      keyPrefix,
      keyName: dto.keyName || null,
      isActive: true,
      expiresAt: dto.expiresAt ? new Date(dto.expiresAt) : null,
      ipAllowlist: dto.ipAllowlist ? JSON.stringify(dto.ipAllowlist) : null,
    });

    const saved = await this.apiKeyRepo.save(apiKey);

    // Never return the hash
    const { keyHash, ...safeApiKey } = saved;

    return {
      apiKey: safeApiKey as Partial<ApiKeyEntity>,
      rawKey,
    };
  }

  /**
   * Rotate an API key — deactivate old one and create new one.
   */
  async rotateApiKey(
    id: string,
    dto?: RotateApiKeyDto,
  ): Promise<{
    apiKey: Partial<ApiKeyEntity>;
    rawKey: string;
  }> {
    const existingKey = await this.apiKeyRepo.findOne({ where: { id } });
    if (!existingKey) {
      throw new NotFoundException(`API key '${id}' not found`);
    }

    if (!existingKey.isActive) {
      throw new BadRequestException('Cannot rotate an already revoked key');
    }

    // Revoke the old key
    existingKey.isActive = false;
    existingKey.revokedAt = new Date();
    await this.apiKeyRepo.save(existingKey);

    // Create a new key for the same client
    return this.createApiKey({
      clientId: existingKey.clientId,
      keyName: existingKey.keyName,
      ipAllowlist: dto?.ipAllowlist
        ? dto.ipAllowlist
        : existingKey.ipAllowlist
          ? JSON.parse(existingKey.ipAllowlist)
          : undefined,
    });
  }

  /**
   * Revoke an API key.
   */
  async revokeApiKey(id: string, revokedBy?: string): Promise<Partial<ApiKeyEntity>> {
    const apiKey = await this.apiKeyRepo.findOne({ where: { id } });
    if (!apiKey) {
      throw new NotFoundException(`API key '${id}' not found`);
    }

    if (!apiKey.isActive) {
      throw new BadRequestException('API key is already revoked');
    }

    apiKey.isActive = false;
    apiKey.revokedAt = new Date();
    apiKey.revokedBy = revokedBy || null;
    const saved = await this.apiKeyRepo.save(apiKey);

    // Never return the hash
    const { keyHash, ...safeApiKey } = saved as ApiKeyEntity;
    return safeApiKey as Partial<ApiKeyEntity>;
  }
}
