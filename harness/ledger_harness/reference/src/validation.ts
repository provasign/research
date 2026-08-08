export interface Validator<T> {
  readonly id: string;
  validate(value: T): string[];
}
