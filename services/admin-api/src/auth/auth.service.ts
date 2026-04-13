/**
 * Auth Service — handles JWT token generation, validation, and user authentication.
 */
import {
  Injectable,
  UnauthorizedException,
  BadRequestException,
  ConflictException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import { AdminUserEntity } from './admin-user.entity';

export interface LoginDto {
  email: string;
  password: string;
}

export interface RegisterAdminDto {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  role?: 'admin' | 'analyst' | 'ops';
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
    role: string;
  };
}

@Injectable()
export class AuthService {
  constructor(
    @InjectRepository(AdminUserEntity)
    private readonly adminUserRepo: Repository<AdminUserEntity>,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
  ) {}

  async login(dto: LoginDto): Promise<AuthResponse> {
    const user = await this.adminUserRepo.findOne({
      where: { email: dto.email.toLowerCase() },
    });

    if (!user) {
      throw new UnauthorizedException('Invalid credentials');
    }

    if (!user.passwordHash) {
      throw new UnauthorizedException(
        'No password set — please use the invite link to set your password first',
      );
    }

    if (user.status === 'suspended') {
      throw new UnauthorizedException('Account is suspended');
    }

    if (user.status === 'invited') {
      throw new UnauthorizedException('Please set your password first using the invite link');
    }

    const isPasswordValid = await bcrypt.compare(dto.password, user.passwordHash);
    if (!isPasswordValid) {
      throw new UnauthorizedException('Invalid credentials');
    }

    // Update last login
    user.lastLoginAt = new Date();
    await this.adminUserRepo.save(user);

    return this.generateTokens(user);
  }

  async refreshToken(refreshToken: string): Promise<{ accessToken: string; expiresIn: number }> {
    try {
      const payload = this.jwtService.verify(refreshToken, {
        secret: this.configService.get<string>('JWT_REFRESH_SECRET', 'dev-refresh-secret-change-in-production'),
      });

      const user = await this.adminUserRepo.findOne({
        where: { id: payload.sub },
      });

      if (!user || user.refreshToken !== refreshToken || user.status !== 'active') {
        throw new UnauthorizedException('Invalid refresh token');
      }

      const accessToken = await this.generateAccessToken(user);

      return {
        accessToken,
        expiresIn: this.configService.get<number>('JWT_EXPIRES_IN_SECONDS', 86400),
      };
    } catch (error) {
      throw new UnauthorizedException('Invalid refresh token');
    }
  }

  async logout(userId: string): Promise<void> {
    await this.adminUserRepo.update(userId, { refreshToken: null });
  }

  async changePassword(userId: string, currentPassword: string, newPassword: string): Promise<void> {
    const user = await this.adminUserRepo.findOne({ where: { id: userId } });
    if (!user) {
      throw new UnauthorizedException('User not found');
    }

    if (user.passwordHash) {
      const isValid = await bcrypt.compare(currentPassword, user.passwordHash);
      if (!isValid) {
        throw new BadRequestException('Current password is incorrect');
      }
    }

    user.passwordHash = await bcrypt.hash(newPassword, 12);
    user.passwordChangedAt = new Date();
    user.refreshToken = null; // Invalidate all existing refresh tokens
    await this.adminUserRepo.save(user);
  }

  async createAdmin(dto: RegisterAdminDto): Promise<AdminUserEntity> {
    const existing = await this.adminUserRepo.findOne({
      where: { email: dto.email.toLowerCase() },
    });

    if (existing) {
      throw new ConflictException('Admin user with this email already exists');
    }

    const passwordHash = dto.password
      ? await bcrypt.hash(dto.password, 12)
      : null;

    const user = this.adminUserRepo.create({
      email: dto.email.toLowerCase(),
      passwordHash,
      firstName: dto.firstName,
      lastName: dto.lastName,
      role: dto.role || 'analyst',
      status: dto.password ? 'active' : 'invited',
    });

    return this.adminUserRepo.save(user);
  }

  async listAdmins(): Promise<AdminUserEntity[]> {
    return this.adminUserRepo.find({
      order: { createdAt: 'DESC' },
      select: [
        'id',
        'email',
        'firstName',
        'lastName',
        'role',
        'status',
        'lastLoginAt',
        'createdAt',
      ],
    });
  }

  async suspendAdmin(userId: string): Promise<AdminUserEntity> {
    const user = await this.adminUserRepo.findOne({ where: { id: userId } });
    if (!user) {
      throw new BadRequestException('Admin user not found');
    }
    user.status = 'suspended';
    user.refreshToken = null;
    return this.adminUserRepo.save(user);
  }

  async reactivateAdmin(userId: string): Promise<AdminUserEntity> {
    const user = await this.adminUserRepo.findOne({ where: { id: userId } });
    if (!user) {
      throw new BadRequestException('Admin user not found');
    }
    user.status = 'active';
    return this.adminUserRepo.save(user);
  }

  // ── Internal methods ──────────────────────────────────────────────

  async validateJwtPayload(payload: any): Promise<any> {
    const user = await this.adminUserRepo.findOne({
      where: { id: payload.sub },
      select: [
        'id',
        'email',
        'firstName',
        'lastName',
        'role',
        'status',
      ],
    });

    if (!user || user.status !== 'active') {
      return null;
    }

    return {
      userId: user.id,
      email: user.email,
      firstName: user.firstName,
      lastName: user.lastName,
      role: user.role,
    };
  }

  async validateUser(email: string): Promise<AdminUserEntity | null> {
    const user = await this.adminUserRepo.findOne({
      where: { email: email.toLowerCase() },
    });
    return user && user.status === 'active' ? user : null;
  }

  private async generateTokens(user: AdminUserEntity): Promise<AuthResponse> {
    const accessToken = await this.generateAccessToken(user);
    const refreshToken = await this.generateRefreshToken(user);

    // Store refresh token in DB
    user.refreshToken = refreshToken;
    await this.adminUserRepo.save(user);

    return {
      accessToken,
      refreshToken,
      expiresIn: this.configService.get<number>('JWT_EXPIRES_IN_SECONDS', 86400),
      user: {
        id: user.id,
        email: user.email,
        firstName: user.firstName,
        lastName: user.lastName,
        role: user.role,
      },
    };
  }

  private async generateAccessToken(user: AdminUserEntity): Promise<string> {
    return this.jwtService.signAsync(
      {
        sub: user.id,
        email: user.email,
        role: user.role,
      },
      {
        secret: this.configService.get<string>('JWT_SECRET', 'dev-jwt-secret-change-in-production'),
        expiresIn: this.configService.get<number>('JWT_EXPIRES_IN_SECONDS', 86400),
      },
    );
  }

  private async generateRefreshToken(user: AdminUserEntity): Promise<string> {
    return this.jwtService.signAsync(
      { sub: user.id },
      {
        secret: this.configService.get<string>('JWT_REFRESH_SECRET', 'dev-refresh-secret-change-in-production'),
        expiresIn: this.configService.get<number>('JWT_REFRESH_EXPIRES_IN_SECONDS', 604800), // 7 days
      },
    );
  }
}
