# Credaly TypeScript SDK

Official TypeScript client for the [Credaly Predictive Behavioral Credit API](https://credaly.com).

## Installation

```bash
npm install @credaly/sdk
```

## Quick Start

```typescript
import { CredalyClient } from '@credaly/sdk';

// Initialize the client
const client = new CredalyClient({
  apiKey: 'credaly_your_api_key_here',
});

// 1. Grant consent before scoring
const consent = await client.grantConsent({
  bvn: '22412345678',
  phone: '+2348012345678',
  dataCategory: 'bureau',
  purpose: 'credit scoring for loan application',
});

// 2. Score a borrower
const result = await client.score({
  bvn: '22412345678',
  phone: '+2348012345678',
  tierConfig: ['formal', 'alternative'],
});

console.log(`Score: ${result.score}`);
console.log(`Confidence: ${result.confidenceBand}`);
console.log(`Data coverage: ${result.dataCoveragePct}%`);
console.log(`Positive factors: ${result.positiveFactors}`);
console.log(`Negative factors: ${result.negativeFactors}`);

// 3. Submit repayment outcome
const outcome = await client.submitOutcome({
  loanId: 'ln_123456',
  bvn: '22412345678',
  disbursementDate: '2026-01-15T00:00:00Z',
  dueDate: '2026-04-15T00:00:00Z',
  loanAmountNgn: 150000,
  outcome: 'REPAID_ON_TIME',
  outcomeDate: '2026-04-10T00:00:00Z',
  scoreAtOrigination: 712,
});
```

## Error Handling

```typescript
import {
  CredalyClient,
  AuthenticationError,
  RateLimitError,
  ValidationError,
  ConsentError,
  ServerError,
} from '@credaly/sdk';

try {
  const result = await client.score({ bvn: '...', phone: '...' });
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Invalid API key');
  } else if (error instanceof RateLimitError) {
    console.error(`Rate limited. Retry after ${error.retryAfter}s`);
  } else if (error instanceof ConsentError) {
    console.error('Consent issue');
  } else if (error instanceof ValidationError) {
    console.error('Bad request');
  } else if (error instanceof ServerError) {
    console.error(`Server error, trace: ${error.traceId}`);
  }
}
```

## API

See [src/types.ts](src/types.ts) for all type definitions.

| Method | Description |
|---|---|
| `score(options)` | Compute credit score |
| `getScoreHistory(bvn)` | Get borrower score history |
| `grantConsent(options)` | Grant data category consent |
| `checkConsentStatus(bvn)` | Check consent status |
| `withdrawConsent(consentId)` | Withdraw consent |
| `submitOutcome(options)` | Submit loan outcome |
| `getSubjectData(bvn)` | DSAR — all borrower data |
| `health()` | API health check |

## License

MIT
