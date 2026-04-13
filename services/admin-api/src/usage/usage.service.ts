/**
 * Lender Usage Service — retrieves API usage metrics from Redis.
 *
 * Architecture:
 * - Scoring API increments Redis counters on every request (middleware)
 * - Admin API reads from Redis for real-time usage
 * - Daily aggregates are stored in PostgreSQL for historical reporting
 *
 * Redis key schema:
 *   usage:{lender_id}:{YYYY-MM-DD}:calls     — total API calls today
 *   usage:{lender_id}:{YYYY-MM-DD}:errors    — total errors today
 *   usage:{lender_id}:{YYYY-MM-DD}:latency   — sum of latencies (for avg calculation)
 *   usage:{lender_id}:{YYYY-MM-DD}:score     — sum of scores computed
 *   rate:{lender_id}                          — current minute request count (TTL 60s)
 */
import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class UsageService {
  private readonly logger = new Logger(UsageService.name);

  constructor(private readonly redisService: RedisService) {}

  /**
   * Get usage statistics for a lender.
   * Reads from Redis counters for the specified period.
   */
  async getUsage(lenderId: string, days: number = 30): Promise<{
    lender_id: string;
    period_days: number;
    summary: {
      total_calls: number;
      total_errors: number;
      error_rate_pct: number;
      avg_latency_ms: number;
      total_scores_computed: number;
    };
    daily: Array<{
      date: string;
      calls: number;
      errors: number;
      avg_latency_ms: number;
    }>;
  }> {
    const redisReady = await this.redisService.isReady();

    if (!redisReady) {
      this.logger.warn('Redis unavailable — returning zeroed usage data');
      return this._zeroedUsage(lenderId, days);
    }

    const today = new Date();
    let totalCalls = 0;
    let totalErrors = 0;
    let totalLatency = 0;
    let totalScores = 0;
    const daily: Array<{ date: string; calls: number; errors: number; avg_latency_ms: number }> = [];

    for (let i = 0; i < days; i++) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];

      const calls = parseInt(
        (await this.redisService.get(`usage:${lenderId}:${dateStr}:calls`)) || '0',
        10,
      );
      const errors = parseInt(
        (await this.redisService.get(`usage:${lenderId}:${dateStr}:errors`)) || '0',
        10,
      );
      const latencySum = parseInt(
        (await this.redisService.get(`usage:${lenderId}:${dateStr}:latency`)) || '0',
        10,
      );
      const scores = parseInt(
        (await this.redisService.get(`usage:${lenderId}:${dateStr}:scores`)) || '0',
        10,
      );

      totalCalls += calls;
      totalErrors += errors;
      totalLatency += latencySum;
      totalScores += scores;

      daily.push({
        date: dateStr,
        calls,
        errors,
        avg_latency_ms: calls > 0 ? Math.round(latencySum / calls) : 0,
      });
    }

    return {
      lender_id: lenderId,
      period_days: days,
      summary: {
        total_calls: totalCalls,
        total_errors: totalErrors,
        error_rate_pct: totalCalls > 0 ? parseFloat(((totalErrors / totalCalls) * 100).toFixed(2)) : 0,
        avg_latency_ms: totalCalls > 0 ? Math.round(totalLatency / totalCalls) : 0,
        total_scores_computed: totalScores,
      },
      daily,
    };
  }

  /**
   * Get rate limit headroom for a lender.
   * Reads the current minute's request count from Redis.
   */
  async getRateLimitHeadroom(lenderId: string, rateLimit: number): Promise<{
    limit: number;
    used: number;
    remaining: number;
    pct_used: number;
    window_reset_seconds: number;
  }> {
    const redisReady = await this.redisService.isReady();

    if (!redisReady) {
      return {
        limit: rateLimit,
        used: 0,
        remaining: rateLimit,
        pct_used: 0,
        window_reset_seconds: 60,
      };
    }

    const used = parseInt(
      (await this.redisService.get(`rate:${lenderId}`)) || '0',
      10,
    );

    // Calculate seconds until the rate limit window resets
    const now = new Date();
    const secondsElapsed = now.getSeconds();
    const windowResetSeconds = 60 - secondsElapsed;

    return {
      limit: rateLimit,
      used,
      remaining: Math.max(0, rateLimit - used),
      pct_used: rateLimit > 0 ? parseFloat(((used / rateLimit) * 100).toFixed(1)) : 0,
      window_reset_seconds: windowResetSeconds,
    };
  }

  /**
   * Record an API call for a lender.
   * Called by the scoring API middleware on every request.
   * This is the write-side of the usage tracking system.
   */
  async recordApiCall(
    lenderId: string,
    latencyMs: number,
    isError: boolean = false,
    isScoreComputation: boolean = false,
  ): Promise<void> {
    const redisReady = await this.redisService.isReady();
    if (!redisReady) {
      return; // Silently skip — don't break the API call
    }

    const today = new Date().toISOString().split('T')[0];

    // Increment today's counters
    await this.redisService.incr(`usage:${lenderId}:${today}:calls`);
    await this.redisService.expire(`usage:${lenderId}:${today}:calls`, 86400 * 7); // Keep for 7 days

    if (isError) {
      await this.redisService.incr(`usage:${lenderId}:${today}:errors`);
      await this.redisService.expire(`usage:${lenderId}:${today}:errors`, 86400 * 7);
    }

    if (latencyMs > 0) {
      await this.redisService.incrby(`usage:${lenderId}:${today}:latency`, Math.round(latencyMs));
      await this.redisService.expire(`usage:${lenderId}:${today}:latency`, 86400 * 7);
    }

    if (isScoreComputation) {
      await this.redisService.incr(`usage:${lenderId}:${today}:scores`);
      await this.redisService.expire(`usage:${lenderId}:${today}:scores`, 86400 * 7);
    }

    // Increment rate limiter counter
    const rateKey = `rate:${lenderId}`;
    const count = await this.redisService.incr(rateKey);

    // Set TTL on first request in the minute window
    if (count === 1) {
      await this.redisService.expire(rateKey, 60);
    }
  }

  /**
   * Get usage for all lenders (admin overview).
   */
  async getAllLendersUsage(days: number = 7): Promise<Array<{
    lender_id: string;
    total_calls: number;
    total_errors: number;
    error_rate_pct: number;
  }>> {
    const redisReady = await this.redisService.isReady();
    if (!redisReady) {
      return [];
    }

    const today = new Date();
    const lenderMap = new Map<string, { calls: number; errors: number }>();

    for (let i = 0; i < days; i++) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];

      // Find all lender usage keys for this date
      const callKeys = await this.redisService.keys(`usage:*:${dateStr}:calls`);

      for (const key of callKeys) {
        const parts = key.split(':');
        const lenderId = parts[1];
        const calls = parseInt((await this.redisService.get(key)) || '0', 10);
        const errors = parseInt(
          (await this.redisService.get(`usage:${lenderId}:${dateStr}:errors`)) || '0',
          10,
        );

        const existing = lenderMap.get(lenderId) || { calls: 0, errors: 0 };
        lenderMap.set(lenderId, {
          calls: existing.calls + calls,
          errors: existing.errors + errors,
        });
      }
    }

    return Array.from(lenderMap.entries()).map(([lenderId, data]) => ({
      lender_id: lenderId,
      total_calls: data.calls,
      total_errors: data.errors,
      error_rate_pct: data.calls > 0 ? parseFloat(((data.errors / data.calls) * 100).toFixed(2)) : 0,
    }));
  }

  private _zeroedUsage(lenderId: string, days: number): any {
    const today = new Date();
    const daily = Array.from({ length: days }, (_, i) => {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      return {
        date: date.toISOString().split('T')[0],
        calls: 0,
        errors: 0,
        avg_latency_ms: 0,
      };
    });

    return {
      lender_id: lenderId,
      period_days: days,
      summary: {
        total_calls: 0,
        total_errors: 0,
        error_rate_pct: 0,
        avg_latency_ms: 0,
        total_scores_computed: 0,
      },
      daily,
    };
  }
}
