/**
 * Roles Decorator — attaches required roles to route handlers.
 * Usage: @Roles('admin', 'ops')
 */
import { SetMetadata } from '@nestjs/common';
import { AdminRole } from '../admin-user.entity';

export const ROLES_KEY = 'roles';
export const Roles = (...roles: AdminRole[]) => SetMetadata(ROLES_KEY, roles);
