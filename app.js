const token = document.querySelector('meta[name="request-token"]').content;
const form = document.querySelector('#factory-form');
const slugInput = document.querySelector('#slug');
const filesEl = document.querySelector('#file-list');
const statusEl = document.querySelector('#status-pill');
const messageEl = document.querySelector('#message');
let timer;
function announce(message) {
  messageEl.textContent = message;
  messageEl.classList.add('show');
  clearTimeout(timer);
  timer = setTimeout(() => messageEl.classList.remove('show'), 3200);
}
function setStatus(label, error = false) {
  statusEl.lastChild.textContent = ` ${label.toUpperCase()}`;
  statusEl.classList.toggle('error', error);
}
function validSlug() { return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slugInput.value) && slugInput.value.length <= 48; }
async function request(path, extra = {}) {
  if (!validSlug()) throw new Error('Use a valid lowercase repository name.');
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json','X-Factory-Request':token}, body:JSON.stringify({slug:slugInput.value,...extra})});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Request failed (${response.status}).`);
  }
  return response;
}
function renderFiles(files) {
  filesEl.replaceChildren();
  for (const [name, digest] of Object.entries(files)) {
    const row = document.createElement('div'); row.className = 'file-row';
    const icon = document.createElement('span'); icon.className = 'file-icon'; icon.textContent = '▧';
    const file = document.createElement('span'); file.className = 'file-name'; file.textContent = name;
    const hash = document.createElement('span'); hash.className = 'file-hash'; hash.textContent = digest;
    row.append(icon,file,hash); filesEl.append(row);
  }
  setStatus(`${Object.keys(files).length} files ready`);
}
function renderTemplates(templates) {
  filesEl.replaceChildren();
  for (const [name, content] of Object.entries(templates)) {
    const details = document.createElement('details'); details.className = 'template-preview';
    const summary = document.createElement('summary'); summary.textContent = name;
    const pre = document.createElement('pre'); pre.textContent = content;
    details.append(summary, pre); filesEl.append(details);
  }
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  try { const data = await (await request('/api/manifest')).json(); renderTemplates(data.templates); setStatus(`${Object.keys(data.files).length} files ready`); announce('Dry run ready. Open each file to review its contents.'); }
  catch (error) { setStatus('Check input', true); announce(error.message); }
});
document.querySelector('#zip-btn').addEventListener('click', async () => {
  try {
    const response = await request('/api/zip'); const blob = await response.blob();
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${slugInput.value}.zip`; link.click(); URL.revokeObjectURL(link.href);
    announce('Starter ZIP downloaded with its manifest.');
  } catch (error) { announce(error.message); }
});
document.querySelector('#generate-btn').addEventListener('click', async () => {
  try {
    const result = await (await request('/api/generate',{dry_run:false})).json();
    setStatus('Generated'); announce(`Created or preserved files in ${result.target}`);
  } catch (error) { setStatus('Failed', true); announce(error.message); }
});
document.querySelector('#verify-btn').addEventListener('click', async () => {
  try {
    const result = await (await request('/api/verify')).json();
    filesEl.replaceChildren();
    for (const [name, value] of Object.entries(result.checks)) {
      const row = document.createElement('div'); row.className = 'file-row';
      const icon = document.createElement('span'); icon.className = 'file-icon'; icon.textContent = value === 'pass' ? '✓' : '!';
      const file = document.createElement('span'); file.className = 'file-name'; file.textContent = name;
      const status = document.createElement('span'); status.className = 'file-hash'; status.textContent = value.toUpperCase();
      row.append(icon,file,status); filesEl.append(row);
    }
    setStatus(result.ok ? 'Integrity passed' : 'Changes found', !result.ok); announce(result.ok ? 'All generated files match the manifest.' : 'Some files differ from the manifest.');
  } catch (error) { setStatus('Verify failed', true); announce(error.message); }
});
