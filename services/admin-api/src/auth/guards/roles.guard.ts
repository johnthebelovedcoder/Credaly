/**
 * Roles Guard — enforces role-based access control.
 * Usage: @UseGuards(JwtAuthGuard, RolesGuard) @Roles('admin', 'ops')
 */
import { Injectable, CanActivate, ExecutionContext, ForbiddenException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ROLES_KEY } from '../decorators/roles.decorator';
import { AdminRole } from '../admin-user.entity';

// Role hierarchy — higher roles implicitly have lower role permissions
const ROLE_HIERARCHY: Record<AdminRole, AdminRole[]> = {
  admin: ['admin', 'analyst', 'ops'],
  ops: ['ops', 'analyst'],
  analyst: ['analyst'],
};

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<AdminRole[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (!requiredRoles || requiredRoles.length === 0) {
      return true; // No roles required — allow
    }

    const request = context.switchToHttp().getRequest();
    const user = request.user;

    if (!user || !user.role) {
      throw new ForbiddenException('Access denied — no role assigned');
    }

    // Check if user's role (or any implied role) is in the required roles
    const userImpliedRoles = ROLE_HIERARCHY[user.role as AdminRole] || [];
    const hasRequiredRole = requiredRoles.some((role) =>
      userImpliedRoles.includes(role),
    );

    if (!hasRequiredRole) {
      throw new ForbiddenException(
        `Access denied — requires one of: ${requiredRoles.join(', ')}`,
      );
    }

    return true;
  }
}
