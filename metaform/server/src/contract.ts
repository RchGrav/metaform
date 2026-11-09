/** Load the project's contract files. They stay the single source; nothing here copies them. */
import { readFileSync } from 'node:fs';
import { Ajv2020, type ErrorObject, type ValidateFunction } from 'ajv/dist/2020.js';

const root = new URL('../../', import.meta.url);
const read = (file: string) => JSON.parse(readFileSync(new URL(file, root), 'utf8'));

export interface Contract {
  tool: { name: string; description: string; inputSchema: Record<string, unknown> };
  validInput: ValidateFunction;
  validElement: ValidateFunction;
}

export function loadContract(): Contract {
  const registry = read('mcp-tools.proposed.json');
  if (registry.tools.length !== 1) throw new Error('The contract must declare exactly one tool');
  const tool = registry.tools[0];
  const ajv = new Ajv2020({ strict: false, allErrors: false });
  return {
    tool,
    validInput: ajv.compile(tool.inputSchema),
    validElement: new Ajv2020({ strict: false }).compile(read('metaform.schema.json')),
  };
}

/** Name the most specific failure. `oneOf` and `anyOf` failures only say that a deeper one exists. */
export function explain(errors: ErrorObject[] | null | undefined): string {
  const specific = (errors ?? []).filter(({ keyword }) => keyword !== 'oneOf' && keyword !== 'anyOf');
  const candidates = specific.length > 0 ? specific : (errors ?? []);
  const deepest = candidates.reduce<ErrorObject | undefined>((best, error) =>
    best === undefined || error.instancePath.length > best.instancePath.length ? error : best, undefined);
  if (deepest === undefined) return 'input is not valid';
  const allowed = deepest.params.allowedValues as unknown[] | undefined;
  const detail = allowed ? `must be one of: ${allowed.join(', ')}` : deepest.message;
  return `${deepest.instancePath || 'input'} ${detail}`;
}
