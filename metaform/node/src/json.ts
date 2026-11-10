// JSON values that keep the order of an object's keys, as the Rust form's `serde_json` does with
// its `preserve_order` feature. A JavaScript object moves keys that look like whole numbers to
// the front, so an object here is a `Map`, and this file has its own parser and writer.
//
// A value is never adjusted after another part of the program holds it. Code that needs a
// different object builds a new `Map`.

export type Json = null | boolean | number | string | Json[] | JsonObject;
export type JsonObject = Map<string, Json>;

/** An object from its entries, in the order given. */
export function obj(...entries: [string, Json][]): JsonObject {
  return new Map(entries);
}

export function isObject(value: Json | undefined): value is JsonObject {
  return value instanceof Map;
}

export function isArray(value: Json | undefined): value is Json[] {
  return Array.isArray(value);
}

/** The entry of an object, or `undefined` when the value is not an object or has no such key. */
export function get(value: Json | undefined, key: string): Json | undefined {
  return value instanceof Map ? value.get(key) : undefined;
}

/** The value as text, or `undefined` when it is not text. */
export function text(value: Json | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

/** Whether two values are equal. The order of an object's keys does not matter. */
export function equal(a: Json | undefined, b: Json | undefined): boolean {
  if (a === b) {
    return true;
  }
  if (Array.isArray(a)) {
    return Array.isArray(b) && a.length === b.length && a.every((item, index) => equal(item, b[index]));
  }
  if (a instanceof Map) {
    if (!(b instanceof Map) || a.size !== b.size) {
      return false;
    }
    for (const [key, value] of a) {
      if (!b.has(key) || !equal(value, b.get(key))) {
        return false;
      }
    }
    return true;
  }
  return false;
}

/** A copy that shares no object or list with the value. */
export function copy(value: Json): Json {
  if (Array.isArray(value)) {
    return value.map(copy);
  }
  if (value instanceof Map) {
    const out: JsonObject = new Map();
    for (const [key, item] of value) {
      out.set(key, copy(item));
    }
    return out;
  }
  return value;
}

/** The value as compact JSON text. */
export function stringify(value: Json): string {
  if (Array.isArray(value)) {
    return `[${value.map(stringify).join(",")}]`;
  }
  if (value instanceof Map) {
    const parts: string[] = [];
    for (const [key, item] of value) {
      parts.push(`${JSON.stringify(key)}:${stringify(item)}`);
    }
    return `{${parts.join(",")}}`;
  }
  return JSON.stringify(value);
}

/** The value as JSON text with two spaces for each level, as `serde_json::to_string_pretty` writes it. */
export function pretty(value: Json, indent = ""): string {
  const inner = `${indent}  `;
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    return `[\n${value.map((item) => inner + pretty(item, inner)).join(",\n")}\n${indent}]`;
  }
  if (value instanceof Map) {
    if (value.size === 0) {
      return "{}";
    }
    const parts: string[] = [];
    for (const [key, item] of value) {
      parts.push(`${inner}${JSON.stringify(key)}: ${pretty(item, inner)}`);
    }
    return `{\n${parts.join(",\n")}\n${indent}}`;
  }
  return JSON.stringify(value);
}

const NUMBER = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;
const SPACE = /[ \t\n\r]*/y;

/** Parse JSON text. Throws `SyntaxError` when the text is not one JSON value. */
export function parse(source: string): Json {
  let at = 0;

  const fail = (what: string): never => {
    throw new SyntaxError(`${what} at character ${at + 1}`);
  };

  const skip = (): void => {
    SPACE.lastIndex = at;
    SPACE.test(source);
    at = SPACE.lastIndex;
  };

  const string = (): string => {
    const start = at;
    at += 1;
    for (;;) {
      const code = source.charCodeAt(at);
      if (Number.isNaN(code)) {
        return fail("the text ends inside a string");
      }
      if (code === 0x22) {
        break;
      }
      at += code === 0x5c ? 2 : 1;
    }
    at += 1;
    const token = source.slice(start, at);
    // The built-in parser checks the escapes and the control characters of one string.
    return token.includes("\\") || /[\u0000-\u001f]/.test(token)
      ? (JSON.parse(token) as string)
      : token.slice(1, -1);
  };

  const value = (): Json => {
    skip();
    const first = source[at];
    if (first === "{") {
      at += 1;
      const out: JsonObject = new Map();
      skip();
      if (source[at] === "}") {
        at += 1;
        return out;
      }
      for (;;) {
        skip();
        if (source[at] !== '"') {
          fail("expected a key");
        }
        const key = string();
        skip();
        if (source[at] !== ":") {
          fail("expected ':'");
        }
        at += 1;
        // A key given twice keeps its first place and takes its last value.
        out.set(key, value());
        skip();
        if (source[at] === ",") {
          at += 1;
        } else if (source[at] === "}") {
          at += 1;
          return out;
        } else {
          fail("expected ',' or '}'");
        }
      }
    }
    if (first === "[") {
      at += 1;
      const out: Json[] = [];
      skip();
      if (source[at] === "]") {
        at += 1;
        return out;
      }
      for (;;) {
        out.push(value());
        skip();
        if (source[at] === ",") {
          at += 1;
        } else if (source[at] === "]") {
          at += 1;
          return out;
        } else {
          fail("expected ',' or ']'");
        }
      }
    }
    if (first === '"') {
      return string();
    }
    for (const [word, result] of [["true", true], ["false", false], ["null", null]] as [string, Json][]) {
      if (source.startsWith(word, at)) {
        at += word.length;
        return result;
      }
    }
    NUMBER.lastIndex = at;
    if (!NUMBER.test(source)) {
      return fail("expected a value");
    }
    const number = Number(source.slice(at, NUMBER.lastIndex));
    if (!Number.isFinite(number)) {
      return fail("the number is out of range");
    }
    at = NUMBER.lastIndex;
    return number;
  };

  const result = value();
  skip();
  if (at !== source.length) {
    fail("text follows the value");
  }
  return result;
}
