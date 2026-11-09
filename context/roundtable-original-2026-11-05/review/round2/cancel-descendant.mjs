// Review reproduction; invokes the existing adapter tool directly. No provider calls.
import { createTools } from '../../adapters/openrouter-acp/dist/tools.js';
import { spawnSync } from 'node:child_process';
const ctl = new AbortController();
let done = false;
const tool = createTools({ sessionId: 'review', root: process.cwd(), client: {
  notify: async () => {},
  request: async () => ({ outcome: { outcome: 'selected', optionId: 'allow' } }),
}}).find(t => t.function.name === 'run_command');
const command = "sleep 30.123456789 & exit 0";
const result = tool.function.execute({command}, {callId:'review',signal:ctl.signal});
result.then(() => {done=true}, () => {done=true});
await new Promise(r => setTimeout(r, 300));
ctl.abort(new Error('review cancellation'));
await new Promise(r => setTimeout(r, 300));
console.log(JSON.stringify({cancelled:ctl.signal.aborted,settled:done}));
// Clean up only descendants of this reproduction, even when the adapter fails.
const ps = spawnSync('ps', ['-eo','pid,ppid,pgid,args'], {encoding:'utf8'}).stdout;
for (const row of ps.split('\n')) {
  const match = row.trim().match(/^(\d+)\s+\d+\s+(\d+)\s+sleep 30\.123456789$/);
  if (match) { try {process.kill(-Number(match[2]), 'SIGKILL')} catch {} }
}
await result.catch(() => {});
