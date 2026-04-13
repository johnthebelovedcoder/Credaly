/**
 * Credaly SDK — typed exception classes.
 */

export class CredalyError extends Error {
  constructor(
    message: string,
    public readonly code?: string,
    public readonly traceId?: string,
  ) {
    super(message);
    this.name = 'CredalyError';
  }
}

export class AuthenticationError extends CredalyError {
  constructor(message: string, code?: string, traceId?: string) {
    super(message, code, traceId);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends CredalyError {
  constructor(
    message: string,
    public readonly retryAfter: number = 60,
    code?: string,
    traceId?: string,
  ) {
    super(message, code, traceId);
    this.name = 'RateLimitError';
  }
}

export class ValidationError extends CredalyError {
  constructor(message: string, code?: string, traceId?: string) {
    super(message, code, traceId);
    this.name = 'ValidationError';
  }
}

export class ConsentError extends CredalyError {
  constructor(message: string, code?: string, traceId?: string) {
    super(message, code, traceId);
    this.name = 'ConsentError';
  }
}

export class NotFoundError extends CredalyError {
  constructor(message: string, code?: string, traceId?: string) {
    super(message, code, traceId);
    this.name = 'NotFoundError';
  }
}

export class ServerError extends CredalyError {
  constructor(message: string, code?: string, traceId?: string) {
    super(message, code, traceId);
    this.name = 'ServerError';
  }
}
