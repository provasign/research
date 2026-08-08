export interface Clock {
  now(): number;
}

export class FixedClock implements Clock {
  readonly at: number;
  constructor(at: number) {
    this.at = at;
  }
  now(): number {
    return this.at;
  }
}

export class SteppingClock implements Clock {
  private start: number;
  private stepMs: number;
  private ticks: number;
  constructor(start: number, stepMs: number) {
    this.start = start;
    this.stepMs = stepMs;
    this.ticks = 0;
  }
  now(): number {
    const v = this.start + this.ticks * this.stepMs;
    this.ticks += 1;
    return v;
  }
}
