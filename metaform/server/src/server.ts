/** The MCP surface: exactly the one tool the contract declares, with its schema sent unchanged. */
import { Server } from '@modelcontextprotocol/server';
import { apply } from './commands.ts';
import { loadContract } from './contract.ts';
import type { Store } from './store.ts';

export function createServer(store: Store): Server {
  const contract = loadContract();
  const server = new Server(
    { name: 'metaform', version: '0.0.0' },
    { capabilities: { tools: {} }, supportedProtocolVersions: ['2026-07-28', '2025-11-25'] },
  );

  server.setRequestHandler('tools/list', async () => ({ tools: [contract.tool as never] }));

  server.setRequestHandler('tools/call', async (request) => {
    if (request.params.name !== contract.tool.name) {
      return { isError: true, content: [{ type: 'text' as const, text: `Unknown tool: ${request.params.name}` }] };
    }
    const { failed, result } = await apply(store, contract, request.params.arguments ?? {});
    return { isError: failed, content: [{ type: 'text' as const, text: JSON.stringify(result) }] };
  });

  return server;
}
