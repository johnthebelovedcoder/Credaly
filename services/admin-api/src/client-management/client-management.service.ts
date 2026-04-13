/**
 * Client Management Service.
 * PRD FR-040, US-007, US-009: create, suspend, terminate lender accounts.
 *
 * SECURITY: Raw API keys are NEVER stored in the database.
 * Only the bcrypt hash is persisted. The raw key is returned once at creation
 * and never retrievable again.
 */
import {
  Injectable,
  NotFoundException,
  ConflictException,
  BadRequestException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';
import { LenderClientEntity } from './lender-client.entity';

export interface CreateLenderClientDto {
  name: string;
  environment: 'sandbox' | 'production';
  tierAccess: string[];
  rateLimit?: number;
  ipAllowlist?: string[];
}

@Injectable()
export class ClientManagementService {
  constructor(
    @InjectRepository(LenderClientEntity)
    private readonly clientRepo: Repository<LenderClientEntity>,
  ) {}

  /**
   * Create a new lender client with API key. PRD US-007.
   *
   * SECURITY NOTES:
   * - Raw API key is generated, hashed, returned ONCE, then discarded.
   * - Only the bcrypt hash is stored in the database.
   * - The key uses a cryptographically secure random generator.
   */
  async createClient(dto: CreateLenderClientDto): Promise<{
    client: Partial<LenderClientEntity>;
    rawApiKey: string;
  }> {
    // Generate cryptographically secure API key
    const rawKey = this.generateSecureApiKey();

    // Hash with bcrypt (12 rounds — matches scoring API)
    const saltRounds = 12;
    const hashedKey = await bcrypt.hash(rawKey, saltRounds);

    const client = this.clientRepo.create({
      name: dto.name,
      apiKeyHash: hashedKey,
      // SECURITY: Do NOT store apiKeyRaw — it's returned once then discarded
      environment: dto.environment,
      tierAccess: JSON.stringify(dto.tierAccess),
      rateLimit: dto.rateLimit || 100,
      ipAllowlist: dto.ipAllowlist ? JSON.stringify(dto.ipAllowlist) : undefined,
      status: 'active',
    });

    const saved = await this.clientRepo.save(client);

    // Return the client (without the hash) and the raw key (shown ONCE)
    const { apiKeyHash, ...clientWithoutHash } = saved;

    return {
      client: clientWithoutHash,
      rawApiKey: rawKey,
    };
  }

  /**
   * List all lender clients with their status.
   */
  async listClients(status?: string): Promise<Partial<LenderClientEntity>[]> {
    const where = status ? { status: status as 'active' | 'suspended' | 'terminated' } : {};
    const clients = await this.clientRepo.find({ where, order: { createdAt: 'DESC' } });

    // Strip sensitive fields
    return clients.map((c) => {
      const { apiKeyHash, ...safe } = c;
      return safe;
    });
  }

  /**
   * Get a single lender client by ID.
   */
  async getClientById(id: string): Promise<Partial<LenderClientEntity>> {
    const client = await this.clientRepo.findOne({ where: { id } });
    if (!client) {
      throw new NotFoundException(`Lender client '${id}' not found`);
    }

    const { apiKeyHash, ...safe } = client;
    return safe;
  }

  /**
   * Suspend a lender client.
   */
  async suspendClient(id: string): Promise<Partial<LenderClientEntity>> {
    const client = await this.getClientById(id);
    await this.clientRepo.update(id, { status: 'suspended' });

    const updated = await this.clientRepo.findOne({ where: { id } });
    if (!updated) throw new NotFoundException(`Client '${id}' not found after update`);

    const { apiKeyHash, ...safe } = updated;
    return safe;
  }

  /**
   * Terminate a lender client.
   */
  async terminateClient(id: string): Promise<Partial<LenderClientEntity>> {
    const client = await this.getClientById(id);
    await this.clientRepo.update(id, { status: 'terminated' });

    const updated = await this.clientRepo.findOne({ where: { id } });
    if (!updated) throw new NotFoundException(`Client '${id}' not found after update`);

    const { apiKeyHash, ...safe } = updated;
    return safe;
  }

  /**
   * Reactivate a suspended client.
   */
  async reactivateClient(id: string): Promise<Partial<LenderClientEntity>> {
    const client = await this.clientRepo.findOne({ where: { id } });
    if (!client) {
      throw new NotFoundException(`Lender client '${id}' not found`);
    }
    if (client.status !== 'suspended') {
      throw new ConflictException(`Cannot reactivate client with status '${client.status}'`);
    }

    await this.clientRepo.update(id, { status: 'active' });

    const updated = await this.clientRepo.findOne({ where: { id } });
    if (!updated) throw new NotFoundException(`Client '${id}' not found after update`);

    const { apiKeyHash, ...safe } = updated;
    return safe;
  }

  /**
   * Rotate API key for a lender client.
   * SECURITY: Old key is invalidated. New key is generated, hashed, returned ONCE.
   */
  async rotateApiKey(id: string): Promise<{
    client: Partial<LenderClientEntity>;
    rawApiKey: string;
  }> {
    const client = await this.clientRepo.findOne({ where: { id } });
    if (!client) {
      throw new NotFoundException(`Lender client '${id}' not found`);
    }

    // Generate new cryptographically secure API key
    const rawKey = this.generateSecureApiKey();

    client.apiKeyHash = await bcrypt.hash(rawKey, 12);
    await this.clientRepo.save(client);

    const { apiKeyHash, ...safe } = client;
    return { client: safe, rawApiKey: rawKey };
  }

  /**
   * Verify an API key against a client's stored hash.
   * Used internally by the auth system.
   */
  async verifyApiKey(clientId: string, rawKey: string): Promise<boolean> {
    const client = await this.clientRepo.findOne({
      where: { id: clientId },
      select: ['id', 'apiKeyHash', 'status'],
    });

    if (!client || client.status !== 'active') {
      return false;
    }

    return bcrypt.compare(rawKey, client.apiKeyHash);
  }

  /**
   * Generate a cryptographically secure API key.
   * Format: credaly_{timestamp}_{256-bit-random}
   */
  private generateSecureApiKey(): string {
    const timestamp = Date.now();
    // 32 bytes = 256 bits of entropy, base64 encoded
    const random = crypto.randomBytes(32).toString('base64url');
    return `credaly_${timestamp}_${random}`;
  }
}
