/* Notes and cited messages, files and searches share this reader. Markdown-it 15.0.3 (bundled, MIT) parses
 * documents into supported DOM nodes. Raw HTML stays text and images never load. */
import {referenceHref, referenceParts} from '/page/app/roundtable/references.js';

const noteQuery = new URLSearchParams(location.search);
const noteProject = noteQuery.get('project') || '';
const noteTable = noteQuery.get('table') || '';
const notePath = noteQuery.get('note') || '';
const noteReference = noteQuery.get('reference') || '';
const noteContext = {project: noteProject, table: noteTable, note: notePath, reference: noteReference};
const noteTitle = document.querySelector('#note-title');
const noteLocation = document.querySelector('#note-location');
const noteStatus = document.querySelector('#note-status');
const noteContent = document.querySelector('#note-content');
const noteRefresh = document.querySelector('#note-refresh');
const noteMarkdown = window.markdownit({html: false, linkify: false, typographer: false});
const noteTags = new Set(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'ul', 'ol', 'li',
  'em', 'strong', 's', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a']);
let noteLoaded = false;

function noteLink(href) {
  return referenceHref(href, noteContext, true);
}

function appendReferences(parent, text) {
  if (/<\/?[a-z][^>]*>/i.test(text)) { parent.append(document.createTextNode(text)); return; }
  for (const part of referenceParts(text, noteContext)) {
    if (!part.href || parent.closest?.('a')) parent.append(document.createTextNode(part.text));
    else {
      const link = document.createElement('a');
      link.href = part.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = part.text;
      parent.append(link);
    }
  }
}

function noteTokens(tokens, parent) {
  const stack = [parent];
  for (const token of tokens) {
    const target = stack[stack.length - 1];
    if (token.type === 'inline') noteTokens(token.children || [], target);
    else if (token.type === 'text' || token.type === 'softbreak') {
      appendReferences(target, token.type === 'softbreak' ? '\n' : token.content);
    } else if (token.type === 'hardbreak' || token.type === 'hr') {
      target.append(document.createElement(token.type === 'hr' ? 'hr' : 'br'));
    } else if (token.type === 'code_inline' || token.type === 'fence' || token.type === 'code_block') {
      const code = document.createElement('code');
      if (token.type === 'code_inline') appendReferences(code, token.content);
      else code.textContent = token.content;
      if (token.type === 'code_inline') target.append(code);
      else {
        const pre = document.createElement('pre');
        pre.append(code);
        target.append(pre);
      }
    } else if (token.type === 'image') {
      const alt = document.createElement('span');
      alt.className = 'note-image-alt';
      alt.textContent = `[Image: ${token.content || 'no description'}]`;
      target.append(alt);
    } else if (token.nesting === 1 && noteTags.has(token.tag)) {
      if (token.hidden) { stack.push(target); continue; }
      const href = token.tag === 'a' ? noteLink(token.attrGet('href')) : null;
      const node = document.createElement(token.tag === 'a' && !href ? 'span' : token.tag);
      if (href) {
        node.setAttribute('href', href);
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
      if (token.tag === 'ol' && /^\d+$/.test(token.attrGet('start') || '')) {
        node.setAttribute('start', token.attrGet('start'));
      }
      if (token.tag === 'td' || token.tag === 'th') {
        const alignment = /^text-align:(left|right|center)$/.exec(token.attrGet('style') || '');
        if (alignment) node.className = `align-${alignment[1]}`;
      }
      target.append(node);
      stack.push(node);
    } else if (token.nesting === -1) {
      if (stack.length > 1) stack.pop();
    } else if (token.content) target.append(document.createTextNode(token.content));
  }
}

async function loadNote() {
  noteRefresh.disabled = true;
  noteContent.setAttribute('aria-busy', 'true');
  noteStatus.textContent = 'Loading…';
  noteStatus.dataset.state = 'loading';
  try {
    const query = new URLSearchParams({project: noteProject, table: noteTable});
    query.set(noteReference ? 'reference' : 'note', noteReference || notePath);
    const response = await fetch(`/api/roundtable?${query}`, {credentials: 'same-origin', cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `The server returned ${response.status}.`);
    if (typeof result.text !== 'string') throw new Error('The server did not return note text.');
    const filename = typeof result.path === 'string' ? result.path : noteReference || notePath;
    if (noteReference) noteContext.reference = filename;
    noteTitle.textContent = filename;
    document.title = `${filename} · Roundtable note`;
    const fragment = document.createDocumentFragment();
    if (noteReference && !/^R[1-9]\d*-[1-9]\d*$/.test(noteReference) && !/\.md(?:[:#]|$)/i.test(filename)) {
      const pre = document.createElement('pre');
      appendReferences(pre, result.text);
      fragment.append(pre);
    } else noteTokens(noteMarkdown.parse(result.text, {}), fragment);
    if (!fragment.childNodes.length) {
      const empty = document.createElement('p');
      empty.textContent = 'This note is empty.';
      fragment.append(empty);
    }
    noteContent.replaceChildren(fragment);
    noteLoaded = true;
    noteLocation.textContent = `${noteProject} · ${noteTable}${result.line ? ` · Line ${result.line}` : ''}`;
    noteStatus.textContent = result.cut
      ? 'This file continues beyond the first 1 MiB shown here.'
      : `Loaded at ${new Date().toLocaleTimeString()}.`;
    noteStatus.dataset.state = result.cut ? 'cut' : 'ready';
  } catch (error) {
    noteStatus.textContent = `Could not load the note: ${error.message || error}`
      + (noteLoaded ? ' The previous version is still shown.' : '');
    noteStatus.dataset.state = 'error';
  } finally {
    noteRefresh.disabled = false;
    noteContent.setAttribute('aria-busy', 'false');
  }
}

noteTitle.textContent = noteReference || notePath || 'Roundtable note';
noteLocation.textContent = `${noteProject} · ${noteTable}`;
noteRefresh.addEventListener('click', loadNote);
if (noteProject && noteTable && (notePath || noteReference)) loadNote();
else {
  noteRefresh.disabled = true;
  noteContent.setAttribute('aria-busy', 'false');
  noteStatus.textContent = 'Choose a note from the roundtable’s Documents list.';
  noteStatus.dataset.state = 'error';
}
