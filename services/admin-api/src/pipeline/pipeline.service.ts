/**
 * Pipeline Health Service.
 */
import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, MoreThanOrEqual } from 'typeorm';
import { DataPipelineRun } from './data-pipeline-run.entity';

@Injectable()
export class PipelineService {
  constructor(
    @InjectRepository(DataPipelineRun)
    private readonly pipelineRepo: Repository<DataPipelineRun>,
  ) {}

  /**
   * Get current health status of all data source pipelines.
   * Returns the most recent run per source.
   */
  async getPipelineHealth(): Promise<any[]> {
    const latestRuns = await this.pipelineRepo
      .createQueryBuilder('run')
      .select('run.source_name', 'sourceName')
      .addSelect('run.status', 'status')
      .addSelect('run.started_at', 'startedAt')
      .addSelect('run.completed_at', 'completedAt')
      .addSelect('run.records_ingested', 'recordsIngested')
      .addSelect('run.error_count', 'errorCount')
      .addSelect('run.error_log', 'errorLog')
      .orderBy('run.created_at', 'DESC')
      .getRawMany();

    // De-duplicate by source_name — keep the latest run per source
    const latest = new Map<string, any>();
    for (const run of latestRuns) {
      if (!latest.has(run.sourceName)) {
        latest.set(run.sourceName, {
          source_name: run.sourceName,
          status: run.status,
          last_run: run.startedAt,
          last_completed: run.completedAt,
          records_ingested: parseInt(run.recordsIngested) || 0,
          error_count: parseInt(run.errorCount) || 0,
          error_log: run.errorLog,
          is_healthy: run.status === 'completed',
        });
      }
    }

    return Array.from(latest.values());
  }

  /**
   * Get pipeline runs for a specific source with pagination.
   */
  async getSourceHistory(
    sourceName: string,
    limit: number = 20,
    offset: number = 0,
  ): Promise<{ runs: DataPipelineRun[]; total: number }> {
    const [runs, total] = await this.pipelineRepo.findAndCount({
      where: { sourceName },
      order: { createdAt: 'DESC' },
      take: limit,
      skip: offset,
    });

    return { runs, total };
  }

  /**
   * Get aggregate pipeline uptime percentage.
   */
  async getPipelineUptime(hours: number = 24): Promise<number> {
    const since = new Date();
    since.setHours(since.getHours() - hours);

    const totalRuns = await this.pipelineRepo.count({
      where: { createdAt: MoreThanOrEqual(since) },
    });
    const healthyRuns = await this.pipelineRepo.count({
      where: { createdAt: MoreThanOrEqual(since), status: 'completed' },
    });

    return totalRuns > 0 ? (healthyRuns / totalRuns) * 100 : 100;
  }
}
