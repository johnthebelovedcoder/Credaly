/**
 * Credaly SDK — TypeScript types mirroring the PRD API spec.
 */

export interface ConfidenceInterval {
  lower: number;
  upper: number;
  level: string; // "95%"
}

export interface ScoreResult {
  score: number;
  confidenceInterval: ConfidenceInterval;
  confidenceBand: 'HIGH' | 'MEDIUM' | 'LOW';
  dataCoveragePct: number;
  positiveFactors: string[];
  negativeFactors: string[];
  consentTokenRef?: string;
  modelVersion: string;
  computedAt: Date;
  traceId: string;
}

export interface ScoreHistoryEntry {
  score: number;
  confidenceBand: 'HIGH' | 'MEDIUM' | 'LOW';
  dataCoveragePct: number;
  modelVersion: string;
  computedAt: Date;
}

export interface ScoreHistoryResult {
  bvnHash: string;
  scores: ScoreHistoryEntry[];
}

export interface ConsentResult {
  consentId: string;
  borrowerBvnHash: string;
  dataCategory: string;
  purpose: string;
  authorizedLenders: string[];
  expiryAt?: Date;
  isActive: boolean;
  tokenSignature: string;
  createdAt: Date;
}

export interface ConsentStatusEntry {
  dataCategory: string;
  isActive: boolean;
  purpose: string;
  expiryAt?: Date;
  grantedAt: Date;
}

export interface ConsentStatusResult {
  borrowerBvnHash: string;
  consents: ConsentStatusEntry[];
  minimumConsentMet: boolean;
}

export interface ConsentWithdrawResult {
  consentId: string;
  status: string;
  withdrawnAt: Date;
  downstreamLendersNotified: string[];
}

export interface OutcomeResult {
  loanId: string;
  status: string;
  message: string;
}

export interface SubjectDataResult {
  bvnHash: string;
  profile: Record<string, unknown>;
  consentRecords: Record<string, unknown>[];
  featureSummary: Record<string, unknown>[];
  scoreHistory: Record<string, unknown>[];
  compiledAt: Date;
}

/** Valid values for API parameters. */
export const TIER_VALUES = ['formal', 'alternative', 'psychographic'] as const;
export type TierValue = (typeof TIER_VALUES)[number];

export const OUTCOME_VALUES = [
  'REPAID_ON_TIME',
  'REPAID_LATE',
  'DEFAULTED',
  'RESTRUCTURED',
  'WRITTEN_OFF',
] as const;
export type OutcomeValue = (typeof OUTCOME_VALUES)[number];

export const CONSENT_CATEGORIES = [
  'bureau',
  'bank',
  'telco',
  'mobile_money',
  'utility',
  'psychographic',
] as const;
export type ConsentCategory = (typeof CONSENT_CATEGORIES)[number];
