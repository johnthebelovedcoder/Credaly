/**
 * Client Management Service Tests
 */
import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { NotFoundException, ConflictException } from '@nestjs/common';
import { ClientManagementService } from './client-management.service';
import { LenderClientEntity } from './lender-client.entity';
import * as bcrypt from 'bcrypt';

const mockClientRepo = () => ({
  findOne: jest.fn(),
  create: jest.fn(),
  save: jest.fn(),
  find: jest.fn(),
  update: jest.fn(),
});

describe('ClientManagementService', () => {
  let service: ClientManagementService;
  let repo: ReturnType<typeof mockClientRepo>;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ClientManagementService,
        { provide: getRepositoryToken(LenderClientEntity), useFactory: mockClientRepo },
      ],
    }).compile();

    service = module.get<ClientManagementService>(ClientManagementService);
    repo = module.get(getRepositoryToken(LenderClientEntity));
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('createClient', () => {
    it('should create a lender with API key shown once', async () => {
      const savedClient: Partial<LenderClientEntity> = {
        id: 'lnd_test',
        name: 'Test Lender',
        apiKeyHash: '$2b$12$hashed',
        environment: 'sandbox',
        status: 'active',
      };

      repo.create.mockReturnValue(savedClient);
      repo.save.mockResolvedValue(savedClient);

      const result = await service.createClient({
        name: 'Test Lender',
        environment: 'sandbox',
        tierAccess: ['formal', 'alternative'],
      });

      expect(result.rawApiKey).toBeDefined();
      expect(result.rawApiKey).toMatch(/^credaly_\d+_/);
      expect(result.client.apiKeyHash).toBeUndefined(); // Hash stripped from response
      expect(result.client.name).toBe('Test Lender');
    });
  });

  describe('listClients', () => {
    it('should return all clients without hashes', async () => {
      const clients: Partial<LenderClientEntity>[] = [
        { id: '1', name: 'Lender 1', apiKeyHash: 'hash1', status: 'active' },
        { id: '2', name: 'Lender 2', apiKeyHash: 'hash2', status: 'suspended' },
      ];

      repo.find.mockResolvedValue(clients);

      const result = await service.listClients();

      expect(result).toHaveLength(2);
      expect(result[0].apiKeyHash).toBeUndefined();
      expect(result[1].apiKeyHash).toBeUndefined();
    });

    it('should filter by status', async () => {
      repo.find.mockResolvedValue([
        { id: '1', name: 'Active Lender', apiKeyHash: 'hash', status: 'active' },
      ]);

      const result = await service.listClients('active');

      expect(repo.find).toHaveBeenCalledWith({
        where: { status: 'active' },
        order: { createdAt: 'DESC' },
      });
    });
  });

  describe('getClientById', () => {
    it('should return client without hash', async () => {
      const client: Partial<LenderClientEntity> = {
        id: '1',
        name: 'Test',
        apiKeyHash: 'hash',
      };
      repo.findOne.mockResolvedValue(client);

      const result = await service.getClientById('1');

      expect(result.apiKeyHash).toBeUndefined();
      expect(result.name).toBe('Test');
    });

    it('should throw if not found', async () => {
      repo.findOne.mockResolvedValue(null);

      await expect(service.getClientById('nonexistent')).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('suspendClient', () => {
    it('should suspend a client', async () => {
      const client: Partial<LenderClientEntity> = {
        id: '1',
        name: 'Test',
        status: 'active',
        apiKeyHash: 'hash',
      };

      repo.findOne.mockResolvedValue(client);
      repo.save.mockResolvedValue({ ...client, status: 'suspended' });

      const result = await service.suspendClient('1');

      expect(result.status).toBe('suspended');
    });
  });

  describe('terminateClient', () => {
    it('should terminate a client', async () => {
      const client: Partial<LenderClientEntity> = {
        id: '1',
        name: 'Test',
        status: 'active',
        apiKeyHash: 'hash',
      };

      repo.findOne.mockResolvedValue(client);
      repo.save.mockResolvedValue({ ...client, status: 'terminated' });

      const result = await service.terminateClient('1');

      expect(result.status).toBe('terminated');
    });
  });

  describe('reactivateClient', () => {
    it('should reactivate a suspended client', async () => {
      const client: Partial<LenderClientEntity> = {
        id: '1',
        status: 'suspended',
        apiKeyHash: 'hash',
      };

      repo.findOne.mockResolvedValue(client);
      repo.save.mockResolvedValue({ ...client, status: 'active' });

      const result = await service.reactivateClient('1');

      expect(result.status).toBe('active');
    });

    it('should reject reactivating non-suspended client', async () => {
      const client: Partial<LenderClientEntity> = {
        id: '1',
        status: 'active',
      };

      repo.findOne.mockResolvedValue(client);

      await expect(service.reactivateClient('1')).rejects.toThrow(
        ConflictException,
      );
    });
  });

  describe('rotateApiKey', () => {
    it('should generate new key and hash it', async () => {
      const client: Partial<LenderClientEntity> = {
        id: '1',
        name: 'Test',
        apiKeyHash: 'old_hash',
      };

      repo.findOne.mockResolvedValue(client);
      repo.save.mockResolvedValue(client);

      const result = await service.rotateApiKey('1');

      expect(result.rawApiKey).toBeDefined();
      expect(result.rawApiKey).toMatch(/^credaly_\d+_/);
      expect(result.client.apiKeyHash).toBeUndefined();
    });
  });

  describe('verifyApiKey', () => {
    it('should return true for correct key', async () => {
      const correctHash = await bcrypt.hash('correct-key', 12);
      repo.findOne.mockResolvedValue({
        id: '1',
        apiKeyHash: correctHash,
        status: 'active',
      });

      const result = await service.verifyApiKey('1', 'correct-key');

      expect(result).toBe(true);
    });

    it('should return false for inactive client', async () => {
      repo.findOne.mockResolvedValue({
        id: '1',
        apiKeyHash: 'hash',
        status: 'suspended',
      });

      const result = await service.verifyApiKey('1', 'any-key');

      expect(result).toBe(false);
    });
  });
});
