/**
 * Lender Client Entity — mirrors lender_client table.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';

@Entity('lender_client')
export class LenderClientEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  name: string;

  @Column({ name: 'api_key_hash', unique: true })
  apiKeyHash: string;

  @Column({ name: 'api_key_raw', nullable: true })
  apiKeyRaw: string;

  @Column({ name: 'tier_access', type: 'text', nullable: true })
  tierAccess: string; // JSON array

  @Column({ name: 'rate_limit', default: 100 })
  rateLimit: number;

  @Column({ name: 'dpa_signed_at', type: 'datetime', nullable: true })
  dpaSignedAt: Date;

  @Column({ default: 'active' })
  status: 'active' | 'suspended' | 'terminated';

  @Column({ default: 'sandbox' })
  environment: 'sandbox' | 'production';

  @Column({ name: 'ip_allowlist', type: 'text', nullable: true })
  ipAllowlist: string | null; // JSON array

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
