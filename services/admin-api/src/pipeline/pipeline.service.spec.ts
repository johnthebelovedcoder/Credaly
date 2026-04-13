/**
 * Admin API — Pipeline Health Service unit test.
 */
import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { PipelineService } from './pipeline.service';
import { DataPipelineRun } from './data-pipeline-run.entity';

describe('PipelineService', () => {
  let service: PipelineService;

  const mockRepository = {
    createQueryBuilder: jest.fn(),
    count: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PipelineService,
        {
          provide: getRepositoryToken(DataPipelineRun),
          useValue: mockRepository,
        },
      ],
    }).compile();

    service = module.get<PipelineService>(PipelineService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('getPipelineHealth', () => {
    it('should return empty array when no pipelines exist', async () => {
      mockRepository.createQueryBuilder.mockReturnValue({
        select: jest.fn().mockReturnThis(),
        addSelect: jest.fn().mockReturnThis(),
        orderBy: jest.fn().mockReturnThis(),
        getRawMany: jest.fn().mockResolvedValue([]),
      });

      const result = await service.getPipelineHealth();
      expect(result).toEqual([]);
    });
  });

  describe('getPipelineUptime', () => {
    it('should return 100 when no runs exist', async () => {
      mockRepository.count.mockResolvedValue(0);
      const result = await service.getPipelineUptime(24);
      expect(result).toBe(100);
    });
  });
});
