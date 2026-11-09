// Execute the actual HTML routing helper against the Rust monitor event's JSON shape.
import {readFile} from 'node:fs/promises';
const html=await readFile('crates/roundtable-web/assets/index.html','utf8');
const source=html.match(/function tableOf\(data\) \{[\s\S]*?\n\}/)[0];
const route=new Function(`${source}; return tableOf;`)();
try {
  console.log(route({harness:{pid:42,id:'table/seat'},capture:'tls',reason:'probe stopped'}));
} catch(error) {
  console.log(`${error.name}: ${error.message}`);
}
