export interface Middleware {
  readonly id: string;
  handle(req: string, next: (r: string) => string): string;
}

export class RequestPipeline {
  private middleware: Middleware[];

  constructor(middleware: Middleware[]) {
    this.middleware = middleware;
  }

  run(req: string): string {
    const step = (i: number): ((r: string) => string) => {
      if (i >= this.middleware.length) {
        return (r: string) => r;
      }
      return (r: string) => this.middleware[i]!.handle(r, step(i + 1));
    };
    return step(0)(req);
  }
}
