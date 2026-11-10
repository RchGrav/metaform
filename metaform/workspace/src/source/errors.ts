import type { Refusal } from "./types";

/** Whether a value is a refusal as the server sends it: `status` "error" and a `code`. */
export function isRefusal(value: unknown): value is Refusal {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { status?: unknown }).status === "error" &&
    typeof (value as { code?: unknown }).code === "string"
  );
}

/** Thrown by a GraphSource when the server refuses a read or a write. It keeps the refusal unchanged. */
export class RefusalError extends Error {
  readonly refusal: Refusal;
  constructor(refusal: Refusal) {
    super(`${refusal.code}: ${refusal.message}`);
    this.name = "RefusalError";
    this.refusal = refusal;
  }
}

/** Thrown when the host or the server cannot be reached, or answers in an unknown form. */
export class TransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TransportError";
  }
}
