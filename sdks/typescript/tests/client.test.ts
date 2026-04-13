/**
 * TypeScript SDK — unit tests.
 */

import MockAdapter from 'axios-mock-adapter';
import { CredalyClient } from '../src/client';
import {
  AuthenticationError,
  ValidationError,
  RateLimitError,
  ConsentError,
  ServerError,
} from '../src/exceptions';

const BASE_URL = 'https://api.credaly.com';
const API_KEY = 'credaly_test_key_12345';

let mock: MockAdapter;
let client: CredalyClient;

beforeEach(() => {
  client = new CredalyClient({ apiKey: API_KEY, baseUrl: BASE_URL });
  mock = new MockAdapter((client as any).http);
});

afterEach(() => {
  mock.restore();
  mock.reset();
});

// ── Score Tests ──────────────────────────────────────────────────────────

describe('CredalyClient.score', () => {
  it('returns a ScoreResult on success', async () => {
    mock.onPost('/v1/score').reply(200, {
      score: 712,
      confidence_interval: { lower: 688, upper: 736, level: '95%' },
      confidence_band: 'HIGH',
      data_coverage_pct: 84.0,
      positive_factors: ['Consistent mobile money inflows'],
      negative_factors: ['Limited alternative data'],
      consent_token_ref: 'cst_xyz789',
      model_version: 'v2.3.1',
      computed_at: '2026-04-09T14:32:00Z',
      trace_id: 'trc_k9mn23',
    });

    const result = await client.score({
      bvn: '22412345678',
      phone: '+2348012345678',
    });

    expect(result.score).toBe(712);
    expect(result.confidenceBand).toBe('HIGH');
    expect(result.dataCoveragePct).toBe(84.0);
    expect(result.confidenceInterval.lower).toBe(688);
    expect(result.traceId).toBe('trc_k9mn23');
  });

  it('throws ValidationError on 422', async () => {
    mock.onPost('/v1/score').reply(422, {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'BVN must contain only digits',
        trace_id: 'trc_err01',
      },
    });

    await expect(
      client.score({ bvn: 'invalid', phone: '+2348012345678' }),
    ).rejects.toThrow(ValidationError);
  });

  it('throws AuthenticationError on 401', async () => {
    mock.onPost('/v1/score').reply(401, {
      error: { code: 'INVALID_API_KEY', message: 'Invalid API key', trace_id: 'trc_err02' },
    });

    await expect(
      client.score({ bvn: '22412345678', phone: '+2348012345678' }),
    ).rejects.toThrow(AuthenticationError);
  });

  it('throws RateLimitError on 429 with retry-after', async () => {
    mock
      .onPost('/v1/score')
      .reply(429, {
        error: { code: 'RATE_LIMITED', message: 'Rate limit exceeded', trace_id: 'trc_err03' },
      }, { 'Retry-After': '30' });

    await expect(
      client.score({ bvn: '22412345678', phone: '+2348012345678' }),
    ).rejects.toThrow(RateLimitError);
  });

  it('validates tier values', async () => {
    await expect(
      client.score({
        bvn: '22412345678',
        phone: '+2348012345678',
        tierConfig: ['invalid_tier' as any],
      }),
    ).rejects.toThrow(/Invalid tier/);
  });
});

// ── Consent Tests ────────────────────────────────────────────────────────

describe('CredalyClient.grantConsent', () => {
  it('returns a ConsentResult on success', async () => {
    mock.onPost('/v1/consent').reply(200, {
      consent_id: 'cst_abc123',
      borrower_bvn_hash: 'hash123',
      data_category: 'bureau',
      purpose: 'credit scoring',
      authorized_lenders: ['lnd_test'],
      expiry_at: null,
      is_active: true,
      token_signature: 'sig_xyz',
      created_at: '2026-04-09T14:32:00Z',
    });

    const result = await client.grantConsent({
      bvn: '22412345678',
      phone: '+2348012345678',
      dataCategory: 'bureau',
      purpose: 'credit scoring',
      authorizedLenders: ['lnd_test'],
    });

    expect(result.consentId).toBe('cst_abc123');
    expect(result.isActive).toBe(true);
    expect(result.tokenSignature).toBe('sig_xyz');
  });

  it('throws ConsentError on 409', async () => {
    mock.onPost('/v1/consent').reply(409, {
      error: { code: 'CONSENT_EXISTS', message: 'Consent already exists', trace_id: 'trc_err04' },
    });

    await expect(
      client.grantConsent({
        bvn: '22412345678',
        phone: '+2348012345678',
        dataCategory: 'bureau',
        purpose: 'credit scoring',
      }),
    ).rejects.toThrow(ConsentError);
  });

  it('validates consent category', async () => {
    await expect(
      client.grantConsent({
        bvn: '22412345678',
        phone: '+2348012345678',
        dataCategory: 'invalid_category' as any,
        purpose: 'test',
      }),
    ).rejects.toThrow(/Invalid dataCategory/);
  });
});

// ── Outcome Tests ────────────────────────────────────────────────────────

describe('CredalyClient.submitOutcome', () => {
  it('returns an OutcomeResult on success', async () => {
    mock.onPost('/v1/outcomes').reply(200, {
      loan_id: 'ln_test_001',
      status: 'received',
      message: 'Outcome recorded successfully',
    });

    const result = await client.submitOutcome({
      loanId: 'ln_test_001',
      bvn: '22412345678',
      disbursementDate: '2026-01-15T00:00:00Z',
      dueDate: '2026-04-15T00:00:00Z',
      loanAmountNgn: 150000,
      outcome: 'REPAID_ON_TIME',
      outcomeDate: '2026-04-10T00:00:00Z',
      scoreAtOrigination: 712,
    });

    expect(result.loanId).toBe('ln_test_001');
    expect(result.status).toBe('received');
  });

  it('validates outcome values', async () => {
    await expect(
      client.submitOutcome({
        loanId: 'ln_test_001',
        bvn: '22412345678',
        disbursementDate: '2026-01-15T00:00:00Z',
        dueDate: '2026-04-15T00:00:00Z',
        loanAmountNgn: 150000,
        outcome: 'INVALID_OUTCOME' as any,
        outcomeDate: '2026-04-10T00:00:00Z',
        scoreAtOrigination: 712,
      }),
    ).rejects.toThrow(/Invalid outcome/);
  });
});

// ── Client Init Tests ────────────────────────────────────────────────────

describe('CredalyClient constructor', () => {
  it('throws on invalid API key', () => {
    expect(() => new CredalyClient({ apiKey: 'invalid_key' })).toThrow(/starts with/);
  });

  it('throws on empty API key', () => {
    expect(() => new CredalyClient({ apiKey: '' })).toThrow(/starts with/);
  });

  it('accepts custom base URL', () => {
    const c = new CredalyClient({ apiKey: API_KEY, baseUrl: 'https://sandbox.credaly.com' });
    expect((c as any).http.defaults.baseURL).toBe('https://sandbox.credaly.com');
  });
});

// ── Health Test ──────────────────────────────────────────────────────────

describe('CredalyClient.health', () => {
  it('returns health status', async () => {
    mock.onGet('/health').reply(200, {
      status: 'ok',
      service: 'Credaly Scoring API',
      version: '1.0.0',
    });

    const result = await client.health();
    expect(result.status).toBe('ok');
  });
});
