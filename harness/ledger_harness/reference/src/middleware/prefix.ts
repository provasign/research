import type { Middleware } from "../middleware.ts";

export class PrefixMiddleware implements Middleware {
  readonly id = "prefix";
  private p: string;
  constructor(p: string) {
    this.p = p;
  }
  handle(req: string, next: (r: string) => string): string {
    return this.p + next(req);
  }
}
