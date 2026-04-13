/**
 * Admin User entity — internal admin users with role-based access.
 */
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export type AdminRole = 'admin' | 'analyst' | 'ops';

export type AdminStatus = 'active' | 'suspended' | 'invited';

@Entity('admin_user')
export class AdminUserEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, unique: true })
  email: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  passwordHash: string | null;

  @Column({ type: 'varchar', length: 255 })
  firstName: string;

  @Column({ type: 'varchar', length: 255 })
  lastName: string;

  @Column({
    type: 'varchar',
    length: 20,
    default: 'analyst',
  })
  role: AdminRole;

  @Column({
    type: 'varchar',
    length: 20,
    default: 'invited',
  })
  status: AdminStatus;

  @Column({ type: 'varchar', length: 128, nullable: true })
  refreshToken: string | null;

  @Column({ type: 'datetime', nullable: true })
  lastLoginAt: Date | null;

  @Column({ type: 'datetime', nullable: true })
  passwordChangedAt: Date | null;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
