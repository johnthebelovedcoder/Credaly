/**
 * Pipeline Health Module — PRD FR-038.
 * GET /admin/pipeline/health — real-time pipeline health per data source.
 */
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { DataPipelineRun } from './data-pipeline-run.entity';
import { PipelineController } from './pipeline.controller';
import { PipelineService } from './pipeline.service';

@Module({
  imports: [TypeOrmModule.forFeature([DataPipelineRun])],
  controllers: [PipelineController],
  providers: [PipelineService],
  exports: [PipelineService],
})
export class PipelineModule {}
