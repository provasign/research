import type { Middleware } from "../middleware.ts";

export class TrimMiddleware implements Middleware {
  readonly id = "trim";
  handle(req: string, next: (r: string) => string): string {
    return next(req.trim());
  }
}
