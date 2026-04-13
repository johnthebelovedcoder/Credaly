/**
 * Admin User Entity — represents users who can access the admin dashboard.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';

export enum UserRole {
  ADMIN = 'admin',
  ANALYST = 'analyst',
  OPS = 'ops',
}

@Entity('admin_user')
export class UserEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  email: string;

  @Column()
  passwordHash: string;

  @Column({ length: 100 })
  firstName: string;

  @Column({ length: 100 })
  lastName: string;

  @Column({
    type: 'enum',
    enum: UserRole,
    default: UserRole.ANALYST,
  })
  role: UserRole;

  @Column({ default: true })
  isActive: boolean;

  @Column({ name: 'last_login_at', type: 'datetime', nullable: true })
  lastLoginAt: Date;

  @Column({ name: 'refresh_token_hash', type: 'text', nullable: true })
  refreshTokenHash: string | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
