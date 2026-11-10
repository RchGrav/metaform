// Text operations that must give what Rust's standard library gives, so that every form of
// Metaform makes the same decision. JavaScript's own `trim`, `\s` and string order differ from
// Rust's in a few characters; the functions here do not.

/** The characters Rust's `char::is_whitespace` accepts: the Unicode property White_Space. */
const SPACE = /\p{White_Space}/u;
const SPACE_AT_START = /^\p{White_Space}+/u;
const SPACE_AT_END = /\p{White_Space}+$/u;
const SPACE_RUN = /\p{White_Space}+/u;

export function isSpace(character: string): boolean {
  return SPACE.test(character);
}

/** Rust's `str::trim`. */
export function trim(value: string): string {
  return value.replace(SPACE_AT_START, "").replace(SPACE_AT_END, "");
}

/** Rust's `str::trim_end`. */
export function trimEnd(value: string): string {
  return value.replace(SPACE_AT_END, "");
}

/** Rust's `str::split_whitespace`: the words between runs of white space. */
export function words(value: string): string[] {
  return value.split(SPACE_RUN).filter((word) => word !== "");
}

/** Rust's `str::lines`: split at LF, drop a CR before it, and give no empty last line. */
export function lines(value: string): string[] {
  const out = value.split("\n");
  if (out[out.length - 1] === "") {
    out.pop();
  }
  return out.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

/** The number of times one character occurs in the text. */
export function count(value: string, character: string): number {
  let found = 0;
  for (let at = value.indexOf(character); at !== -1; at = value.indexOf(character, at + 1)) {
    found += 1;
  }
  return found;
}

/** A UTF-16 unit moved so that units compare in the order of the characters they encode. */
function rank(unit: number): number {
  if (unit < 0xd800) {
    return unit;
  }
  return unit < 0xe000 ? unit + 0x2000 : unit - 0x800;
}

/**
 * Rust's order of two strings, which is the order of their characters' numbers. JavaScript's `<`
 * compares UTF-16 units and differs for characters above U+FFFF.
 */
export function compare(a: string, b: string): number {
  const shared = Math.min(a.length, b.length);
  for (let at = 0; at < shared; at += 1) {
    const x = a.charCodeAt(at);
    const y = b.charCodeAt(at);
    if (x !== y) {
      return rank(x) < rank(y) ? -1 : 1;
    }
  }
  return a.length === b.length ? 0 : a.length < b.length ? -1 : 1;
}

/**
 * A map whose keys are read in order, as Rust's `BTreeMap<String, V>` gives them. The sorted
 * list of keys is made when it is first read and kept until a key is added or removed.
 */
export class Sorted<V> {
  private items: Map<string, V>;
  private order: readonly string[] | null;

  constructor(from?: Sorted<V>) {
    this.items = new Map(from?.items);
    this.order = from ? from.order : [];
  }

  get size(): number {
    return this.items.size;
  }

  has(key: string): boolean {
    return this.items.has(key);
  }

  get(key: string): V | undefined {
    return this.items.get(key);
  }

  set(key: string, value: V): void {
    if (!this.items.has(key)) {
      this.order = null;
    }
    this.items.set(key, value);
  }

  delete(key: string): void {
    if (this.items.delete(key)) {
      this.order = null;
    }
  }

  /** The keys in order. The caller must not adjust the list. */
  keys(): readonly string[] {
    this.order ??= [...this.items.keys()].sort(compare);
    return this.order;
  }

  *entries(): Generator<[string, V]> {
    for (const key of this.keys()) {
      yield [key, this.items.get(key) as V];
    }
  }

  /** The values in no stated order, for a question that does not depend on order. */
  values(): IterableIterator<V> {
    return this.items.values();
  }
}
