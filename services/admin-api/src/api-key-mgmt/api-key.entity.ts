/**
 * API Key Entity — manages API keys for clients.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';

@Entity('api_key')
export class ApiKeyEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'client_id' })
  clientId: string;

  @Column({ name: 'key_hash', unique: true })
  keyHash: string;

  @Column({ name: 'key_prefix', length: 20 })
  keyPrefix: string; // First 20 chars of raw key for identification

  @Column({ name: 'key_name', nullable: true })
  keyName: string; // User-defined label

  @Column({ default: true })
  isActive: boolean;

  @Column({ name: 'last_used_at', type: 'datetime', nullable: true })
  lastUsedAt: Date;

  @Column({ name: 'expires_at', type: 'datetime', nullable: true })
  expiresAt: Date;

  @Column({ name: 'revoked_at', type: 'datetime', nullable: true })
  revokedAt: Date;

  @Column({ name: 'revoked_by', type: 'varchar', length: 36, nullable: true })
  revokedBy: string | null;

  @Column({ name: 'ip_allowlist', type: 'text', nullable: true })
  ipAllowlist: string | null; // JSON array

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
