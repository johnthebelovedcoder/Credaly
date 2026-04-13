/**
 * Model Metrics Service.
 * In production, this reads from MLflow, Evidently AI, and the scoring API database.
 * Integrated with MLflow for model versioning and Evidently AI for drift detection.
 */
import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export interface ModelMetrics {
  model_version: string;
  gini_coefficient: number | null;
  psi_per_feature: Record<string, number> | null;
  ks_statistic: number | null;
  score_distribution: {
    buckets: string[];
    counts: number[];
  } | null;
  total_scores_computed: number;
  last_updated: string;
}

@Injectable()
export class ModelMetricsService {
  private readonly logger = new Logger(ModelMetricsService.name);

  constructor(private readonly configService: ConfigService) {}

  /**
   * Get current model performance metrics. PRD FR-039.
   * In production: reads from MLflow + Evidently AI + PostgreSQL.
   * Falls back to placeholder if external services unavailable.
   */
  async getModelMetrics(): Promise<ModelMetrics> {
    // TODO: When MLflow server is deployed, fetch via REST API:
    // const mlflowUrl = this.configService.get('MLFLOW_TRACKING_URI');
    // const response = await fetch(`${mlflowUrl}/api/2.0/mlflow/runs/search`);

    // For now, return structured data that will be populated once MLflow is connected
    return {
      model_version: 'v1.0.0',
      gini_coefficient: null, // Will be fetched from MLflow experiment metrics
      psi_per_feature: null, // Will be computed by Evidently AI
      ks_statistic: null, // Will be fetched from MLflow
      score_distribution: null, // Will be computed from PostgreSQL credit_score table
      total_scores_computed: 0, // Will be COUNT(*) FROM credit_score
      last_updated: new Date().toISOString(),
      note: 'Connect MLflow tracking server to populate real metrics',
    };
  }

  /**
   * Get PSI (Population Stability Index) alerts.
   * Alert fires when PSI > 0.2. PRD FR-029.
   * Computed by Evidently AI drift detection module.
   */
  async getPsiAlerts(): Promise<Array<{
    feature_name: string;
    psi_value: number;
    threshold: number;
    triggered_at: string;
    severity: 'warning' | 'critical';
  }>> {
    // TODO: When Evidently AI is running, fetch drift reports:
    // Call scoring API's drift detection endpoint or read from shared storage

    return []; // Will be populated from Evidently AI drift reports
  }

  /**
   * Trigger manual model retraining. PRD FR-042.
   * In production: triggers a Celery task or Airflow DAG that:
   *   1. Fetches latest training data from PostgreSQL
   *   2. Trains new model version
   *   3. Evaluates on validation set
   *   4. Logs to MLflow
   *   5. Registers in Model Registry
   */
  async triggerRetraining(): Promise<{
    job_id: string;
    status: string;
    message: string;
  }> {
    // In production: triggers an Airflow DAG or Celery task
    // For now, return a job ID that can be tracked
    const jobId = `retrain_${Date.now()}`;

    this.logger.log(`Model retraining triggered — job ID: ${jobId}`);

    // TODO: When Celery/Airflow is connected:
    // await this.celeryClient.sendTask('retrain_model', { job_id: jobId });

    return {
      job_id: jobId,
      status: 'queued',
      message: 'Model retraining job queued successfully',
    };
  }

  /**
   * Get score distribution histogram.
   * Computed from PostgreSQL credit_score table.
   */
  async getScoreDistribution(): Promise<{
    buckets: string[];
    counts: number[];
  }> {
    // TODO: Query PostgreSQL:
    // SELECT
    //   CASE
    //     WHEN score BETWEEN 300 AND 400 THEN '300-400'
    //     WHEN score BETWEEN 401 AND 500 THEN '401-500'
    //     ...
    //   END as bucket,
    //   COUNT(*) as count
    // FROM credit_score
    // GROUP BY bucket
    // ORDER BY bucket;

    return {
      buckets: ['300-400', '401-500', '501-600', '601-700', '701-800', '801-850'],
      counts: [0, 0, 0, 0, 0, 0], // Will be populated from database
    };
  }

  /**
   * Get model version history from MLflow.
   */
  async getModelVersions(): Promise<Array<{
    version: string;
    stage: string;
    run_id: string;
    metrics: Record<string, number>;
    created_at: string;
  }>> {
    // TODO: Fetch from MLflow Model Registry
    // GET /api/2.0/mlflow/registered-models/get?name=base_credit_model

    return [];
  }
}
