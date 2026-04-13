/**
 * Credaly TypeScript SDK — strongly typed API client.
 *
 * Usage:
 *   import { CredalyClient } from '@credaly/sdk';
 *
 *   const client = new CredalyClient({ apiKey: 'credaly_xxx' });
 *   const result = await client.score({ bvn: '224...', phone: '+234...' });
 *   console.log(`Score: ${result.score}, Band: ${result.confidenceBand}`);
 */

export { CredalyClient } from './client';
export * from './types';
export * from './exceptions';
