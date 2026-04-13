/**
 * Pipeline Health Entity — mirrors data_pipeline_run from the scoring API.
 */
import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';

@Entity('data_pipeline_run')
export class DataPipelineRun {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'source_name' })
  sourceName: string;

  @Column({ name: 'status' })
  status: 'pending' | 'running' | 'completed' | 'failed' | 'degraded';

  @Column({ name: 'started_at', type: 'datetime', nullable: true })
  startedAt: Date;

  @Column({ name: 'completed_at', type: 'datetime', nullable: true })
  completedAt: Date;

  @Column({ name: 'records_ingested', default: 0 })
  recordsIngested: number;

  @Column({ name: 'error_count', default: 0 })
  errorCount: number;

  @Column({ name: 'error_log', type: 'text', nullable: true })
  errorLog: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
