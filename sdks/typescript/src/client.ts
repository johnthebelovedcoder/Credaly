/**
 * Credaly SDK — main TypeScript client class.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  ScoreResult,
  ConfidenceInterval,
  ScoreHistoryResult,
  ScoreHistoryEntry,
  ConsentResult,
  ConsentStatusResult,
  ConsentStatusEntry,
  ConsentWithdrawResult,
  OutcomeResult,
  SubjectDataResult,
  TierValue,
  OutcomeValue,
  ConsentCategory,
  TIER_VALUES,
  OUTCOME_VALUES,
  CONSENT_CATEGORIES,
} from './types';
import {
  CredalyError,
  AuthenticationError,
  RateLimitError,
  ValidationError,
  ConsentError,
  NotFoundError,
  ServerError,
} from './exceptions';

const DEFAULT_BASE_URL = 'https://api.credaly.com';
const DEFAULT_TIMEOUT = 30000; // ms
const DEFAULT_MAX_RETRIES = 3;

export interface CredalyClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
}

export interface ScoreOptions {
  bvn: string;
  phone: string;
  tierConfig?: TierValue[];
  loanAmountNgn?: number;
  loanTenureDays?: number;
}

export interface ConsentOptions {
  bvn: string;
  phone: string;
  dataCategory: ConsentCategory;
  purpose: string;
  authorizedLenders?: string[];
  expiryDate?: string;
  policyVersion?: string;
}

export interface OutcomeOptions {
  loanId: string;
  bvn: string;
  disbursementDate: string;
  dueDate: string;
  loanAmountNgn: number;
  outcome: OutcomeValue;
  outcomeDate: string;
  scoreAtOrigination: number;
}

function parseDate(value?: string): Date | undefined {
  if (!value) return undefined;
  return new Date(value);
}

export class CredalyClient {
  private readonly http: AxiosInstance;
  private readonly maxRetries: number;

  constructor(options: CredalyClientOptions) {
    if (!options.apiKey || !options.apiKey.startsWith('credaly_')) {
      throw new Error("apiKey must be a valid Credaly API key (starts with 'credaly_')");
    }

    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;

    this.http = axios.create({
      baseURL: (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, ''),
      timeout: options.timeout ?? DEFAULT_TIMEOUT,
      headers: {
        'X-API-Key': options.apiKey,
        'Content-Type': 'application/json',
        'User-Agent': 'credaly-typescript-sdk/1.0.0',
      },
    });

    // Response interceptor for error mapping
    this.http.interceptors.response.use(
      (res) => res,
      (error: AxiosError) => {
        if (error.response) {
          const status = error.response.status;
          const data = error.response.data as any;
          const errorObj = data?.error ?? {};
          const code = errorObj.code ?? 'UNKNOWN';
          const message = errorObj.message ?? error.message;
          const traceId = errorObj.trace_id;

          if (status === 401 || status === 403) {
            return Promise.reject(new AuthenticationError(message, code, traceId));
          }
          if (status === 400 || status === 422) {
            return Promise.reject(new ValidationError(message, code, traceId));
          }
          if (status === 429) {
            const retryAfter = parseInt(
              error.response.headers['retry-after'] ?? '60',
              10,
            );
            return Promise.reject(new RateLimitError(message, retryAfter, code, traceId));
          }
          if (status === 409) {
            return Promise.reject(new ConsentError(message, code, traceId));
          }
          if (status === 404) {
            return Promise.reject(new NotFoundError(message, code, traceId));
          }
          if (status >= 500) {
            return Promise.reject(new ServerError(message, code, traceId));
          }
        }
        return Promise.reject(error);
      },
    );
  }

  private async request<T>(
    method: 'get' | 'post' | 'delete',
    path: string,
    data?: unknown,
  ): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const response = await this.http.request({
          method,
          url: path,
          ...(method !== 'get' && data ? { data } : { params: data }),
        });
        return response.data as T;
      } catch (error: any) {
        if (error instanceof CredalyError) {
          // Don't retry auth, validation, consent, or not-found errors
          if (
            error instanceof AuthenticationError ||
            error instanceof ValidationError ||
            error instanceof ConsentError ||
            error instanceof NotFoundError
          ) {
            throw error;
          }
          lastError = error;
        } else if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
          lastError = error;
        } else {
          throw error;
        }

        // Backoff before retry
        if (attempt < this.maxRetries - 1) {
          await new Promise((resolve) => setTimeout(resolve, 2 ** attempt * 1000));
        }
      }
    }

    throw lastError ?? new ServerError('Request failed after maximum retries', 'MAX_RETRIES_EXCEEDED');
  }

  // ── Scoring ──────────────────────────────────────────────────────────

  /**
   * Compute a credit score for a borrower. PRD Section 8.1.
   */
  async score(options: ScoreOptions): Promise<ScoreResult> {
    if (options.tierConfig) {
      for (const tier of options.tierConfig) {
        if (!TIER_VALUES.includes(tier)) {
          throw new Error(`Invalid tier '${tier}'. Must be one of: ${TIER_VALUES.join(', ')}`);
        }
      }
    }

    const body: Record<string, unknown> = {
      bvn: options.bvn,
      phone: options.phone,
      lender_id: 'auto', // Resolved server-side from API key
      tier_config: options.tierConfig ?? ['formal', 'alternative', 'psychographic'],
    };
    if (options.loanAmountNgn != null) body.loan_amount_ngn = options.loanAmountNgn;
    if (options.loanTenureDays != null) body.loan_tenure_days = options.loanTenureDays;

    const data = await this.request<Record<string, any>>('post', '/v1/score', body);
    const ci = data.confidence_interval as ConfidenceInterval;

    return {
      score: data.score,
      confidenceInterval: ci,
      confidenceBand: data.confidence_band,
      dataCoveragePct: data.data_coverage_pct,
      positiveFactors: data.positive_factors,
      negativeFactors: data.negative_factors,
      consentTokenRef: data.consent_token_ref,
      modelVersion: data.model_version,
      computedAt: parseDate(data.computed_at)!,
      traceId: data.trace_id,
    };
  }

  /**
   * Get the credit score history for a borrower. PRD US-004.
   */
  async getScoreHistory(bvn: string): Promise<ScoreHistoryResult> {
    const data = await this.request<Record<string, any>>('get', `/v1/score/${bvn}/history`);

    const scores: ScoreHistoryEntry[] = (data.scores ?? []).map((s: any) => ({
      score: s.score,
      confidenceBand: s.confidence_band,
      dataCoveragePct: s.data_coverage_pct,
      modelVersion: s.model_version,
      computedAt: parseDate(s.computed_at)!,
    }));

    return {
      bvnHash: data.bvn_hash,
      scores,
    };
  }

  // ── Consent ──────────────────────────────────────────────────────────

  /**
   * Grant consent for a specific data category. PRD FR-011.
   */
  async grantConsent(options: ConsentOptions): Promise<ConsentResult> {
    if (!CONSENT_CATEGORIES.includes(options.dataCategory)) {
      throw new Error(
        `Invalid dataCategory '${options.dataCategory}'. Must be one of: ${CONSENT_CATEGORIES.join(', ')}`,
      );
    }

    const body: Record<string, unknown> = {
      bvn: options.bvn,
      phone: options.phone,
      data_category: options.dataCategory,
      purpose: options.purpose,
      authorized_lenders: options.authorizedLenders ?? [],
      policy_version: options.policyVersion ?? '1.0',
    };
    if (options.expiryDate) body.expiry_date = options.expiryDate;

    const data = await this.request<Record<string, any>>('post', '/v1/consent', body);

    return {
      consentId: data.consent_id,
      borrowerBvnHash: data.borrower_bvn_hash,
      dataCategory: data.data_category,
      purpose: data.purpose,
      authorizedLenders: data.authorized_lenders,
      expiryAt: parseDate(data.expiry_at),
      isActive: data.is_active,
      tokenSignature: data.token_signature,
      createdAt: parseDate(data.created_at)!,
    };
  }

  /**
   * Check the consent status for a borrower.
   */
  async checkConsentStatus(bvn: string): Promise<ConsentStatusResult> {
    const data = await this.request<Record<string, any>>('get', `/v1/consent/${bvn}/status`);

    const consents: ConsentStatusEntry[] = (data.consents ?? []).map((c: any) => ({
      dataCategory: c.data_category,
      isActive: c.is_active,
      purpose: c.purpose,
      expiryAt: parseDate(c.expiry_at),
      grantedAt: parseDate(c.granted_at)!,
    }));

    return {
      borrowerBvnHash: data.borrower_bvn_hash,
      consents,
      minimumConsentMet: data.minimum_consent_met,
    };
  }

  /**
   * Withdraw previously granted consent. PRD FR-014.
   */
  async withdrawConsent(consentId: string, reason?: string): Promise<ConsentWithdrawResult> {
    const body = reason ? { reason } : undefined;
    const data = await this.request<Record<string, any>>('delete', `/v1/consent/${consentId}`, body);

    return {
      consentId: data.consent_id,
      status: data.status,
      withdrawnAt: parseDate(data.withdrawn_at)!,
      downstreamLendersNotified: data.downstream_lenders_notified ?? [],
    };
  }

  // ── Outcomes ─────────────────────────────────────────────────────────

  /**
   * Submit a loan repayment outcome. PRD Section 8.2.
   */
  async submitOutcome(options: OutcomeOptions): Promise<OutcomeResult> {
    if (!OUTCOME_VALUES.includes(options.outcome)) {
      throw new Error(
        `Invalid outcome '${options.outcome}'. Must be one of: ${OUTCOME_VALUES.join(', ')}`,
      );
    }

    const body = {
      loan_id: options.loanId,
      bvn: options.bvn,
      disbursement_date: options.disbursementDate,
      due_date: options.dueDate,
      loan_amount_ngn: options.loanAmountNgn,
      outcome: options.outcome,
      outcome_date: options.outcomeDate,
      score_at_origination: options.scoreAtOrigination,
    };

    const data = await this.request<Record<string, any>>('post', '/v1/outcomes', body);

    return {
      loanId: data.loan_id,
      status: data.status,
      message: data.message,
    };
  }

  // ── Data Subject Rights ──────────────────────────────────────────────

  /**
   * Retrieve all data held about a borrower (DSAR). PRD FR-017.
   */
  async getSubjectData(bvn: string): Promise<SubjectDataResult> {
    const data = await this.request<Record<string, any>>('get', `/v1/subject/${bvn}/data`);

    return {
      bvnHash: data.bvn_hash,
      profile: data.profile,
      consentRecords: data.consent_records,
      featureSummary: data.feature_summary,
      scoreHistory: data.score_history,
      compiledAt: parseDate(data.compiled_at)!,
    };
  }

  // ── Utility ──────────────────────────────────────────────────────────

  /** Check API health. */
  async health(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('get', '/health');
  }
}
