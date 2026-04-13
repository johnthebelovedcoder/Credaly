/**
 * Redis Service — connection management and common operations.
 * Used for: API usage tracking, rate limiting headroom, caching.
 */
import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  private client: Redis;

  constructor(private readonly configService: ConfigService) {}

  async onModuleInit() {
    const redisUrl = this.configService.get<string>(
      'REDIS_URL',
      'redis://localhost:6379/1',
    );

    this.client = new Redis(redisUrl, {
      maxRetriesPerRequest: 3,
      retryStrategy: (times) => {
        if (times > 3) {
          this.logger.warn('Redis max retries exceeded, falling back to memory');
          return null; // Return null to stop retrying
        }
        return Math.min(times * 200, 2000); // Exponential backoff
      },
    });

    this.client.on('connect', () => {
      this.logger.log('Redis connected');
    });

    this.client.on('error', (error) => {
      this.logger.error(`Redis connection error: ${error.message}`);
    });

    this.client.on('ready', () => {
      this.logger.log('Redis ready');
    });
  }

  async onModuleDestroy() {
    if (this.client) {
      await this.client.quit();
      this.logger.log('Redis connection closed');
    }
  }

  getClient(): Redis {
    return this.client;
  }

  async isReady(): Promise<boolean> {
    try {
      const status = this.client.status;
      return status === 'ready' || status === 'connecting';
    } catch {
      return false;
    }
  }

  // ── Convenience methods ──────────────────────────────────────────────

  async get(key: string): Promise<string | null> {
    try {
      return await this.client.get(key);
    } catch (error) {
      this.logger.error(`Redis GET failed for ${key}: ${error.message}`);
      return null;
    }
  }

  async set(key: string, value: string, ttl?: number): Promise<void> {
    try {
      if (ttl) {
        await this.client.setex(key, ttl, value);
      } else {
        await this.client.set(key, value);
      }
    } catch (error) {
      this.logger.error(`Redis SET failed for ${key}: ${error.message}`);
    }
  }

  async incr(key: string): Promise<number> {
    try {
      return await this.client.incr(key);
    } catch (error) {
      this.logger.error(`Redis INCR failed for ${key}: ${error.message}`);
      return 0;
    }
  }

  async incrby(key: string, increment: number): Promise<number> {
    try {
      return await this.client.incrby(key, increment);
    } catch (error) {
      this.logger.error(`Redis INCRBY failed for ${key}: ${error.message}`);
      return 0;
    }
  }

  async expire(key: string, ttl: number): Promise<boolean> {
    try {
      const result = await this.client.expire(key, ttl);
      return result === 1;
    } catch (error) {
      this.logger.error(`Redis EXPIRE failed for ${key}: ${error.message}`);
      return false;
    }
  }

  async del(key: string): Promise<void> {
    try {
      await this.client.del(key);
    } catch (error) {
      this.logger.error(`Redis DEL failed for ${key}: ${error.message}`);
    }
  }

  async keys(pattern: string): Promise<string[]> {
    try {
      return await this.client.keys(pattern);
    } catch (error) {
      this.logger.error(`Redis KEYS failed for ${pattern}: ${error.message}`);
      return [];
    }
  }
}
