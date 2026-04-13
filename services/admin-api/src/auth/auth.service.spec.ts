/**
 * Comprehensive Auth Service Tests
 */
import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcrypt';
import { AuthService } from './auth.service';
import { AdminUserEntity } from './admin-user.entity';

const mockAdminUserRepo = () => ({
  findOne: jest.fn(),
  create: jest.fn(),
  save: jest.fn(),
  update: jest.fn(),
  find: jest.fn(),
});

const mockJwtService = () => ({
  signAsync: jest.fn(),
  verify: jest.fn(),
});

const mockConfigService = () => ({
  get: jest.fn((key: string, defaultValue: any) => defaultValue),
});

describe('AuthService', () => {
  let service: AuthService;
  let userRepo: ReturnType<typeof mockAdminUserRepo>;
  let jwtService: ReturnType<typeof mockJwtService>;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthService,
        { provide: getRepositoryToken(AdminUserEntity), useFactory: mockAdminUserRepo },
        { provide: JwtService, useFactory: mockJwtService },
        { provide: ConfigService, useFactory: mockConfigService },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    userRepo = module.get(getRepositoryToken(AdminUserEntity));
    jwtService = module.get(JwtService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('login', () => {
    it('should return auth response with valid credentials', async () => {
      const mockUser: Partial<AdminUserEntity> = {
        id: 'test-user-id',
        email: 'test@credaly.io',
        passwordHash: await bcrypt.hash('securePassword123', 12),
        firstName: 'Test',
        lastName: 'User',
        role: 'admin',
        status: 'active',
        refreshToken: null,
        lastLoginAt: null,
      };

      userRepo.findOne.mockResolvedValue(mockUser);
      userRepo.save.mockResolvedValue(mockUser);
      jwtService.signAsync.mockResolvedValue('mock.jwt.token');

      const result = await service.login({
        email: 'test@credaly.io',
        password: 'securePassword123',
      });

      expect(result.accessToken).toBeDefined();
      expect(result.user.email).toBe('test@credaly.io');
      expect(userRepo.save).toHaveBeenCalled(); // lastLoginAt updated
    });

    it('should reject invalid credentials', async () => {
      userRepo.findOne.mockResolvedValue(null);

      await expect(
        service.login({ email: 'wrong@credaly.io', password: 'wrong' }),
      ).rejects.toThrow('Invalid credentials');
    });

    it('should reject suspended users', async () => {
      userRepo.findOne.mockResolvedValue({
        id: 'suspended-user',
        email: 'suspended@credaly.io',
        passwordHash: await bcrypt.hash('password', 12),
        status: 'suspended',
      });

      await expect(
        service.login({ email: 'suspended@credaly.io', password: 'password' }),
      ).rejects.toThrow('Account is suspended');
    });

    it('should reject invited users who have not set password', async () => {
      userRepo.findOne.mockResolvedValue({
        id: 'invited-user',
        email: 'invited@credaly.io',
        passwordHash: null,
        status: 'invited',
      });

      await expect(
        service.login({ email: 'invited@credaly.io', password: 'anything' }),
      ).rejects.toThrow('set your password');
    });
  });

  describe('refreshToken', () => {
    it('should return new access token with valid refresh token', async () => {
      const mockUser: Partial<AdminUserEntity> = {
        id: 'test-user-id',
        email: 'test@credaly.io',
        refreshToken: 'valid-refresh-token',
        status: 'active',
      };

      userRepo.findOne.mockResolvedValue(mockUser);
      jwtService.verify.mockReturnValue({ sub: 'test-user-id' });
      jwtService.signAsync.mockResolvedValue('new-access-token');

      const result = await service.refreshToken('valid-refresh-token');

      expect(result.accessToken).toBe('new-access-token');
    });

    it('should reject invalid refresh token', async () => {
      jwtService.verify.mockImplementation(() => {
        throw new Error('Invalid token');
      });

      await expect(service.refreshToken('invalid-token')).rejects.toThrow(
        'Invalid refresh token',
      );
    });
  });

  describe('logout', () => {
    it('should clear refresh token', async () => {
      userRepo.update.mockResolvedValue({ affected: 1 });
      await service.logout('user-id');
      expect(userRepo.update).toHaveBeenCalledWith('user-id', {
        refreshToken: null,
      });
    });
  });

  describe('createAdmin', () => {
    it('should create a new admin user', async () => {
      userRepo.findOne.mockResolvedValue(null); // no existing user
      const newUser: Partial<AdminUserEntity> = {
        id: 'new-user-id',
        email: 'new@credaly.io',
        firstName: 'New',
        lastName: 'User',
        role: 'analyst',
        status: 'active',
      };
      userRepo.create.mockReturnValue(newUser);
      userRepo.save.mockResolvedValue(newUser);

      const result = await service.createAdmin({
        email: 'new@credaly.io',
        password: 'securePassword',
        firstName: 'New',
        lastName: 'User',
        role: 'analyst',
      });

      expect(result.email).toBe('new@credaly.io');
      expect(userRepo.create).toHaveBeenCalled();
      expect(userRepo.save).toHaveBeenCalled();
    });

    it('should reject duplicate email', async () => {
      userRepo.findOne.mockResolvedValue({ id: 'existing', email: 'dup@credaly.io' });

      await expect(
        service.createAdmin({
          email: 'dup@credaly.io',
          password: 'pass',
          firstName: 'Dup',
          lastName: 'User',
        }),
      ).rejects.toThrow('already exists');
    });
  });

  describe('changePassword', () => {
    it('should update password and clear refresh token', async () => {
      const mockUser: Partial<AdminUserEntity> = {
        id: 'user-id',
        passwordHash: await bcrypt.hash('oldPassword', 12),
        refreshToken: 'some-token',
      };

      userRepo.findOne.mockResolvedValue(mockUser);
      userRepo.save.mockResolvedValue(mockUser);

      await service.changePassword('user-id', 'oldPassword', 'newPassword');

      expect(userRepo.save).toHaveBeenCalled();
      expect(mockUser.refreshToken).toBeNull(); // Refresh tokens cleared
    });

    it('should reject incorrect current password', async () => {
      const mockUser: Partial<AdminUserEntity> = {
        id: 'user-id',
        passwordHash: await bcrypt.hash('oldPassword', 12),
      };

      userRepo.findOne.mockResolvedValue(mockUser);

      await expect(
        service.changePassword('user-id', 'wrongPassword', 'newPassword'),
      ).rejects.toThrow('incorrect');
    });
  });
});
