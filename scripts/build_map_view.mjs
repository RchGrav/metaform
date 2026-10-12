// Build the MCP Apps views' files, MCP-037: the official MCP Apps SDK for the views, and the map view itself.
//
// 1. src/metaform/modules/mcp/resources/views/ext-apps.js: the App class of @modelcontextprotocol/ext-apps, the SDK
//    the MCP Apps project publishes for views, from its release file `dist/src/app-with-deps.js` (the SDK with zod and
//    the MCP client protocol bundled in) turned into one classic script that sets `window.McpApps`, so an inline
//    script can use it. Its license is written beside it. The repository keeps both: the node view needs nothing built.
// 2. src/metaform/modules/mcp/resources/views/map.html, the map view, ui://metaform/map: the web GUI's own page as one
//    HTML document. An AI tool shows an MCP App in a sandboxed frame whose content policy loads nothing from
//    elsewhere: only inline scripts and styles run (MCP Apps 2026-01-26, the host's restrictive default). The page is
//    ES modules joined by an import map, so its code is bundled into one inline module, as the MCP Apps examples do
//    with a bundler; everything else, its stylesheet, theme script, Mermaid for the 2D map, the SDK, the views' bridge,
//    the page's frame code and the mcp module's map.js after it, is put in as it is. The page's own files are the only source: nothing of the map is
//    written again for the view. The repository does not keep it; the wheel build makes it (scripts/hatch_views.py)
//    and the MCP server serves the node view in its place where it is missing or older than the page.
//
// Run from the repository: npm --prefix scripts ci, then node scripts/build_map_view.mjs. The map view records the
// files it was built from and their SHA-256, which the server compares with the files installed beside it.
import * as esbuild from 'esbuild';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {dirname, join, relative, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const scripts = dirname(fileURLToPath(import.meta.url));
const modules = join(scripts, '..', 'src', 'metaform', 'modules');
const web = join(modules, 'web');
const views = join(modules, 'mcp', 'resources', 'views');
const require = createRequire(import.meta.url);

// 1. The SDK. Its package.json `exports` name app-with-deps as the build with its dependencies in it.
const sdkPackage = JSON.parse(readFileSync(join(scripts, 'node_modules', '@modelcontextprotocol', 'ext-apps',
  'package.json'), 'utf8'));
const sdkEntry = require.resolve('@modelcontextprotocol/ext-apps/app-with-deps');
const sdk = await esbuild.build({entryPoints: [sdkEntry], bundle: true, format: 'iife', globalName: 'McpApps',
  minify: true, write: false, logLevel: 'warning', target: 'es2022', legalComments: 'none'});
const sdkBanner = `/* @modelcontextprotocol/ext-apps ${sdkPackage.version}, the MCP Apps SDK for views, from its release file ` +
  `dist/src/app-with-deps.js, as one classic script that sets window.McpApps. Written by scripts/build_map_view.mjs; ` +
  `license in ext-apps.LICENSE. */\n`;
writeFileSync(join(views, 'ext-apps.js'), sdkBanner + sdk.outputFiles[0].text);
const zodLicense = readFileSync(join(scripts, 'node_modules', 'zod', 'LICENSE'), 'utf8');
writeFileSync(join(views, 'ext-apps.LICENSE'), readFileSync(join(dirname(dirname(dirname(sdkEntry))), 'LICENSE'),
  'utf8') + `\n---\n\nThe file bundles zod, under this license:\n\n${zodLicense}`);

// 2. The map view. Every file it is made of is hashed, by its path under src/metaform/modules and its bytes.
const inputs = [];
const hash = createHash('sha256');
const source = path => {
  const bytes = readFileSync(path);
  const name = relative(modules, path).split(sep).join('/');
  if (!inputs.includes(name)) { inputs.push(name); hash.update(name).update('\0').update(bytes).update('\0'); }
  return bytes.toString('utf8');
};

// The page's import map is how the browser resolves the page's imports; the bundle resolves them the same way.
const page = source(join(web, 'page', 'index.html'));
const imports = JSON.parse(page.match(/<script type="importmap">([\s\S]*?)<\/script>/)[1]).imports;
const local = url => join(web, url.startsWith('/page/') ? 'page' : 'vendor', url.replace(/^\/(page|vendor)\//, ''));
const importMap = {name: 'import-map', setup(build) {
  build.onResolve({filter: /.*/}, args => {
    if (args.path in imports) return {path: local(imports[args.path])};
    const prefix = Object.keys(imports).find(key => key.endsWith('/') && args.path.startsWith(key));
    if (prefix) return {path: local(imports[prefix] + args.path.slice(prefix.length))};
    if (args.path.startsWith('/page/') || args.path.startsWith('/vendor/')) return {path: local(args.path)};
    return undefined;
  });
  build.onLoad({filter: /\.m?js$/}, args => ({contents: source(args.path), loader: 'js'}));
}};
const bundled = await esbuild.build({entryPoints: [join(web, 'page', 'app.js')], bundle: true, format: 'esm',
  minify: true, write: false, plugins: [importMap], logLevel: 'warning', target: 'es2022'});

// Inline text that the HTML parser would otherwise end early: a closing script tag or a comment opener in the code.
const inline = text => text.replace(/<\/(script)/gi, '<\\/$1').replace(/<!--/g, '<\\!--');
// The page's fonts are files a frame cannot load: the host's fonts stand in where it gives them (frame.js), else the
// page's own fallbacks, the system's sans and mono.
const css = source(join(web, 'page', 'app.css')).replace(/@font-face\{[^}]*\}/g, '');
const body = page.match(/<body>([\s\S]*)<\/body>/)[1].replace(/<script\b[^>]*>[\s\S]*?<\/script>\s*/g, '');
const script = path => `<script>${inline(source(path))}</script>`;
const code = inline(bundled.outputFiles[0].text);
const head = [join(web, 'page', 'theme.js'), join(views, 'ext-apps.js'), join(views, 'bridge.js'),
  join(web, 'page', 'frame.js'), join(views, 'map.js')].map(script).join('\n');
const mermaid = script(join(web, 'vendor', 'mermaid.min.js'));
const recorded = JSON.stringify({sha256: hash.digest('hex'), files: inputs});
const built = `<!doctype html>
<html lang="en" class="frame" data-theme="space">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Metaform map</title>
<!-- The map view, ui://metaform/map, built by scripts/build_map_view.mjs from the web GUI's page. -->
<script type="application/json" id="metaform-view-inputs">${recorded}</script>
<script type="application/json" id="metaform-view">{}</script>
<style>${css}</style>
${head}
</head>
<body>
${body}
${mermaid}
<script type="module">${code}</script>
</body>
</html>
`;
const target = join(views, 'map.html');
writeFileSync(target, built);
console.log(`${target}: ${(statSync(target).size / 1e6).toFixed(1)} MB from ${inputs.length} files`);
