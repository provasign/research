import type { Middleware } from "../middleware.ts";

export class UpperMiddleware implements Middleware {
  readonly id = "upper";
  handle(req: string, next: (r: string) => string): string {
    return next(req).toUpperCase();
  }
}
