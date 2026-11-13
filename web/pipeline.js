// Owner A frontend extension module (A-01 PDF/DOCX Upload + ATS Preview, D1..D5).
// Mounts into #pipelineExtensions without modifying web/app.js or web/index.html.
(function () {
  const mount = document.getElementById('pipelineExtensions');
  if (!mount) return;

  function esc(value) {
    if (typeof escapeHTML === 'function') return escapeHTML(value);
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]));
  }

  function showNotice(msg) {
    if (typeof notice === 'function') {
      notice(msg);
    } else {
      const box = document.getElementById('pipelineUploadStatus');
      if (box) box.textContent = msg;
    }
  }

  function bytesToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    const chunkSize = 0x8000;
    const chunks = [];
    for (let i = 0; i < bytes.length; i += chunkSize) {
      chunks.push(String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize)));
    }
    return btoa(chunks.join(''));
  }

  mount.innerHTML = `
    <div class="paneltop">
      <h2>Pipeline Extensions (Owner A)</h2>
      <span class="pill" id="pipelineStatusPill">Checking adapters...</span>
    </div>
    <p class="small">Upload a <strong>.pdf</strong>, <strong>.docx</strong>, or <strong>.txt</strong> resume in memory to extract text into your profile and inspect the raw ATS reading order (D2).</p>
    <div class="actions">
      <label class="upload">Choose PDF / DOCX / TXT
        <input id="pipelineResumeFile" type="file" accept=".pdf,.docx,.txt,.md">
      </label>
      <button id="pipelineUploadBtn" type="button">Upload &amp; Parse</button>
    </div>
    <p class="small" id="pipelineUploadStatus">No file selected yet (binary JSON upload cap ~145 KB).</p>
    <div id="pipelineAtsPreview"></div>
  `;

  const statusPill = document.getElementById('pipelineStatusPill');
  const fileInput = document.getElementById('pipelineResumeFile');
  const uploadBtn = document.getElementById('pipelineUploadBtn');
  const statusText = document.getElementById('pipelineUploadStatus');
  const previewBox = document.getElementById('pipelineAtsPreview');

  async function refreshPipelineStatus() {
    try {
      const resp = await fetch('/api/pipeline/status');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Status check failed');
      const m = data.model_adapter || {};
      const llmLabel = m.configured
        ? `LLM: ${m.active_provider} (${m.active_model})`
        : 'LLM: offline (set API key in .env)';
      statusPill.textContent = llmLabel;
    } catch (err) {
      statusPill.textContent = 'Pipeline status unavailable';
    }
  }

  fileInput.addEventListener('change', () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      statusText.textContent = 'No file selected yet.';
      return;
    }
    const kb = (file.size / 1024).toFixed(1);
    statusText.textContent = `Selected: ${file.name} (${kb} KB)`;
  });

  uploadBtn.addEventListener('click', async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      showNotice('Choose a .pdf, .docx, or .txt resume file first.');
      return;
    }
    uploadBtn.disabled = true;
    try {
      const buffer = await file.arrayBuffer();
      const contentBase64 = bytesToBase64(buffer);
      if (contentBase64.length > 190000) {
        throw new Error('Encoded file exceeds 200 KB server JSON cap. Use a smaller text PDF, DOCX, or TXT.');
      }
      const resp = await fetch('/api/pipeline/resume/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          content_base64: contentBase64,
          save_to_profile: true,
        }),
      });
      const result = await resp.json();
      if (!resp.ok) throw new Error(result.error || 'Resume upload failed');

      const resumeEl = document.getElementById('resume');
      if (resumeEl) resumeEl.value = result.extracted_text || '';
      if (typeof reload === 'function') await reload();

      const diag = result.ats_diagnostics || {};
      const warnings = Array.isArray(diag.warnings) ? diag.warnings : [];
      const shaShort = String(result.resume_sha256 || '').slice(0, 12);
      statusText.textContent = `Parsed ${result.filename} (${result.char_count} chars, SHA-256 ${shaShort}...) and saved to local profile.`;
      previewBox.innerHTML = `
        <div class="fit">
          <strong>ATS Linearization Preview (D2)</strong>
          <small>Raw reading order (${esc(diag.line_count ?? 0)} lines) — verify columns &amp; dates before applying.</small>
          ${warnings.length ? `<p class="small"><strong>Warnings:</strong> ${warnings.map(esc).join(' | ')}</p>` : '<p class="small">No layout linearization warnings detected.</p>'}
          <pre style="white-space:pre-wrap;max-height:220px;overflow:auto;margin:8px 0 0;font-size:12px;">${esc(result.ats_preview_text || '')}</pre>
        </div>
      `;
      showNotice(`Uploaded ${result.filename} (${result.char_count} chars).`);
    } catch (err) {
      statusText.textContent = err.message;
      showNotice(err.message);
    } finally {
      uploadBtn.disabled = false;
    }
  });

  refreshPipelineStatus();
})();
