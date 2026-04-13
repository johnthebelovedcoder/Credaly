/**
 * Auth Controller — handles login, token refresh, logout, and admin user management.
 */
import {
  Controller,
  Post,
  Get,
  Body,
  HttpCode,
  HttpStatus,
  UseGuards,
  Request,
  BadRequestException,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { AuthService, LoginDto, RegisterAdminDto } from './auth.service';
import { JwtAuthGuard } from './guards/jwt-auth.guard';

@ApiTags('auth')
@Controller('admin/auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Login with email and password' })
  async login(@Body() dto: LoginDto) {
    return this.authService.login(dto);
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Refresh access token using refresh token' })
  async refresh(@Body('refreshToken') refreshToken: string) {
    if (!refreshToken) {
      throw new BadRequestException('Refresh token is required');
    }
    return this.authService.refreshToken(refreshToken);
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Logout and invalidate refresh token' })
  async logout(@Request() req) {
    await this.authService.logout(req.user.userId);
    return { message: 'Logged out successfully' };
  }

  @Post('change-password')
  @HttpCode(HttpStatus.OK)
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Change current user password' })
  async changePassword(
    @Request() req,
    @Body() body: { currentPassword: string; newPassword: string },
  ) {
    await this.authService.changePassword(
      req.user.userId,
      body.currentPassword,
      body.newPassword,
    );
    return { message: 'Password changed successfully' };
  }

  @Post('me')
  @HttpCode(HttpStatus.OK)
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get current user profile' })
  async getMe(@Request() req) {
    return req.user;
  }

  // ── Admin user management (requires admin role) ───────────────────

  @Post('users')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Create a new admin user (admin only)' })
  async createAdminUser(@Body() dto: RegisterAdminDto) {
    return this.authService.createAdmin(dto);
  }

  @Get('users')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'List all admin users (admin only)' })
  async listAdminUsers() {
    return this.authService.listAdmins();
  }

  @Post('users/:id/suspend')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Suspend an admin user (admin only)' })
  async suspendAdminUser(id: string) {
    return this.authService.suspendAdmin(id);
  }

  @Post('users/:id/reactivate')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Reactivate a suspended admin user (admin only)' })
  async reactivateAdminUser(id: string) {
    return this.authService.reactivateAdmin(id);
  }
}
