// Owner A frontend extension module (A-01 PDF/DOCX Upload + ATS Preview, A-02 Discovery + D1 Pre-Flight).
// Mounts into #pipelineExtensions without modifying web/app.js, web/index.html, or web/styles.css.
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

  function safeParseJson(raw) {
    if (!raw) return null;
    if (typeof raw === 'object') return raw;
    try {
      return JSON.parse(raw);
    } catch (_err) {
      return null;
    }
  }

  async function postJson(url, payload) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `Request failed (${resp.status})`);
    return data;
  }

  function badgeHtml(label, tone) {
    const tones = {
      good: 'background:#e8f7ee;color:#116337;border:1px solid #9ad3b0;',
      warn: 'background:#fff6e0;color:#8a5200;border:1px solid #f0cc7a;',
      danger: 'background:#fdecec;color:#9b1c1c;border:1px solid #f5aaaa;',
      neutral: 'background:#eef2f7;color:#334155;border:1px solid #cbd5e1;',
    };
    const style = tones[tone] || tones.neutral;
    return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;margin-right:6px;${style}">${esc(label)}</span>`;
  }

  function toneForLiveness(status) {
    if (status === 'active') return 'good';
    if (status === 'stale_risk' || status === 'unknown') return 'warn';
    if (status === 'closed') return 'danger';
    return 'neutral';
  }

  function toneForScam(risk) {
    if (risk === 'low') return 'good';
    if (risk === 'medium') return 'warn';
    if (risk === 'high') return 'danger';
    return 'neutral';
  }

  function toneForRoi(roi) {
    if (roi === 'high_roi_low_bot_noise') return 'good';
    if (roi === 'saturated_easy_apply') return 'warn';
    if (roi === 'high_risk') return 'danger';
    return 'neutral';
  }

  mount.innerHTML = `
    <div class="paneltop">
      <h2>Pipeline Extensions (Owner A)</h2>
      <span class="pill" id="pipelineStatusPill">Checking adapters...</span>
    </div>

    <div style="border-bottom:1px solid rgba(128,128,128,0.22);padding-bottom:12px;margin-bottom:12px;">
      <p class="small"><strong>A-01 Resume Intake &amp; ATS Linearization (D2):</strong> Upload a <strong>.pdf</strong>, <strong>.docx</strong>, or <strong>.txt</strong> resume in memory to extract text into your profile and inspect raw ATS reading order.</p>
      <div class="actions">
        <label class="upload">Choose PDF / DOCX / TXT
          <input id="pipelineResumeFile" type="file" accept=".pdf,.docx,.txt,.md">
        </label>
        <button id="pipelineUploadBtn" type="button">Upload &amp; Parse</button>
      </div>
      <p class="small" id="pipelineUploadStatus">No file selected yet (binary JSON upload cap ~145 KB).</p>
      <div id="pipelineAtsPreview"></div>
    </div>

    <div style="border-bottom:1px solid rgba(128,128,128,0.22);padding-bottom:12px;margin-bottom:12px;">
      <p class="small"><strong>A-02 Public Job Discovery:</strong> Search public ATS feeds (Greenhouse, Lever, Ashby) and optional Serper web discovery (deduplicated + D1 scored).</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-bottom:8px;">
        <input id="pipelineDiscoverQuery" type="text" placeholder="Role query (e.g. Solutions Engineer)">
        <input id="pipelineDiscoverLocation" type="text" placeholder="Location (e.g. Remote, Seattle)">
        <input id="pipelineDiscoverBoards" type="text" placeholder="ATS boards (e.g. greenhouse:stripe, lever:figma)">
      </div>
      <div class="actions">
        <button id="pipelineDiscoverBtn" type="button">Discover Public Jobs</button>
        <span class="small" id="pipelineDiscoverStatus">Ready to search public boards / Serper.</span>
      </div>

      <p class="small" style="margin-top:12px;"><strong>Smart URL Intake:</strong> Parse public Greenhouse / Lever / Ashby / JSON-LD URLs, or fall back cleanly to pasted JD if a site blocks bots or requires login.</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
        <input id="pipelineImportUrl" type="url" placeholder="https://boards.greenhouse.io/... or public job URL" style="flex:1 1 280px;">
        <button id="pipelineImportUrlBtn" type="button">Smart Import URL</button>
      </div>
      <p class="small" id="pipelineImportStatus"></p>

      <div id="pipelineManualFallbackBox" class="fit" style="display:none;margin-top:8px;">
        <strong>Manual Fallback Required (No Login/CAPTCHA Bypass)</strong>
        <p class="small" id="pipelineFallbackReason"></p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin:8px 0;">
          <input id="pipelineFallbackTitle" type="text" placeholder="Job Title (required)">
          <input id="pipelineFallbackCompany" type="text" placeholder="Company Name">
        </div>
        <textarea id="pipelineFallbackDescription" rows="4" placeholder="Paste the full job description text here..."></textarea>
        <div class="actions" style="margin-top:8px;">
          <button id="pipelineFallbackSaveBtn" type="button">Save Pasted Job + Run D1</button>
          <button id="pipelineFallbackCancelBtn" type="button">Dismiss</button>
        </div>
      </div>
    </div>

    <div>
      <div class="paneltop">
        <strong>D1 Pre-Flight Shield (All Saved Jobs)</strong>
        <button id="pipelinePreflightAllBtn" type="button">Run D1 Pre-Flight on All Jobs</button>
      </div>
      <p class="small">Inspects ATS family, liveness window (&gt;30d stale risk / expired), scam red flags, and application friction ROI.</p>
      <div id="pipelinePreflightBoard"></div>
    </div>
  `;

  const statusPill = document.getElementById('pipelineStatusPill');
  const fileInput = document.getElementById('pipelineResumeFile');
  const uploadBtn = document.getElementById('pipelineUploadBtn');
  const statusText = document.getElementById('pipelineUploadStatus');
  const previewBox = document.getElementById('pipelineAtsPreview');

  const discoverQueryEl = document.getElementById('pipelineDiscoverQuery');
  const discoverLocationEl = document.getElementById('pipelineDiscoverLocation');
  const discoverBoardsEl = document.getElementById('pipelineDiscoverBoards');
  const discoverBtn = document.getElementById('pipelineDiscoverBtn');
  const discoverStatus = document.getElementById('pipelineDiscoverStatus');

  const importUrlEl = document.getElementById('pipelineImportUrl');
  const importUrlBtn = document.getElementById('pipelineImportUrlBtn');
  const importStatus = document.getElementById('pipelineImportStatus');

  const fallbackBox = document.getElementById('pipelineManualFallbackBox');
  const fallbackReason = document.getElementById('pipelineFallbackReason');
  const fallbackTitle = document.getElementById('pipelineFallbackTitle');
  const fallbackCompany = document.getElementById('pipelineFallbackCompany');
  const fallbackDesc = document.getElementById('pipelineFallbackDescription');
  const fallbackSaveBtn = document.getElementById('pipelineFallbackSaveBtn');
  const fallbackCancelBtn = document.getElementById('pipelineFallbackCancelBtn');

  const preflightAllBtn = document.getElementById('pipelinePreflightAllBtn');
  const preflightBoard = document.getElementById('pipelinePreflightBoard');

  let pendingFallbackUrl = '';

  async function refreshPipelineStatus() {
    try {
      const resp = await fetch('/api/pipeline/status');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Status check failed');
      const m = data.model_adapter || {};
      const d = data.discovery_adapter || {};
      const llmLabel = m.configured
        ? `LLM: ${m.active_provider} (${m.active_model})`
        : 'LLM: offline';
      const serperLabel = d.serper_configured ? 'Serper: ready' : 'Serper: ATS-only';
      statusPill.textContent = `${llmLabel} | ${serperLabel}`;
    } catch (_err) {
      statusPill.textContent = 'Pipeline status unavailable';
    }
  }

  async function renderPreflightBoard() {
    try {
      const resp = await fetch('/api/jobs');
      const jobs = await resp.json();
      if (!Array.isArray(jobs) || jobs.length === 0) {
        preflightBoard.innerHTML = '<p class="small">No saved jobs yet. Seed demo data or discover/import a job above.</p>';
        return;
      }
      preflightBoard.innerHTML = jobs.map((job) => {
        const pf = job.preflight || safeParseJson(job.preflight_json);
        const ats = job.ats_family || 'unknown';
        const locPart = job.location ? ` · ${esc(job.location)}` : '';
        const salPart = job.salary_text ? ` · ${esc(job.salary_text)}` : '';
        const badges = pf
          ? [
              badgeHtml(`ATS: ${ats}`, ats === 'unknown' ? 'neutral' : 'good'),
              badgeHtml(`Liveness: ${pf.liveness_status}`, toneForLiveness(pf.liveness_status)),
              badgeHtml(`Scam: ${pf.scam_risk}`, toneForScam(pf.scam_risk)),
              badgeHtml(`ROI: ${pf.friction_roi}`, toneForRoi(pf.friction_roi)),
            ].join('')
          : badgeHtml('Pre-Flight Pending', 'neutral') + badgeHtml(`ATS: ${ats}`, 'neutral');

        const flags = pf && Array.isArray(pf.scam_flags) && pf.scam_flags.length
          ? `<div class="small" style="color:#9b1c1c;margin-top:4px;">Flags: ${pf.scam_flags.map(esc).join(', ')}</div>`
          : '';
        const notes = pf && pf.notes
          ? `<div class="small" style="margin-top:4px;">${esc(pf.notes)}</div>`
          : '';

        return `
          <div class="fit" style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;flex-wrap:wrap;">
              <div>
                <strong>${esc(job.title || '(Untitled)')}</strong> — ${esc(job.company || 'Unknown company')}
                <span class="small">${locPart}${salPart}</span>
              </div>
              <button type="button" data-preflight-job-id="${esc(job.id)}">Check D1</button>
            </div>
            <div style="margin-top:6px;">${badges}</div>
            ${flags}
            ${notes}
          </div>
        `;
      }).join('');
    } catch (err) {
      preflightBoard.innerHTML = `<p class="small">${esc(err.message)}</p>`;
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
      const result = await postJson('/api/pipeline/resume/upload', {
        filename: file.name,
        content_base64: contentBase64,
        save_to_profile: true,
      });

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

  discoverBtn.addEventListener('click', async () => {
    discoverBtn.disabled = true;
    discoverStatus.textContent = 'Searching public ATS boards & Serper...';
    try {
      const result = await postJson('/api/pipeline/jobs/discover', {
        query: discoverQueryEl.value.trim(),
        location: discoverLocationEl.value.trim(),
        boards: discoverBoardsEl.value.trim(),
        limit: 12,
        save: true,
      });
      const meta = result.metadata || {};
      const errs = []
        .concat(meta.board_errors || [])
        .concat(meta.serper_error ? [meta.serper_error] : []);
      const warnSuffix = errs.length ? ` (warnings: ${errs.join('; ')})` : '';
      discoverStatus.textContent = `Found ${result.discovered_count} jobs, inserted ${result.inserted_count}, skipped ${result.duplicate_count} duplicates${warnSuffix}.`;
      if (typeof reload === 'function') await reload();
      await renderPreflightBoard();
      showNotice(`Discovery complete: ${result.inserted_count} new jobs added.`);
    } catch (err) {
      discoverStatus.textContent = err.message;
      showNotice(err.message);
    } finally {
      discoverBtn.disabled = false;
    }
  });

  importUrlBtn.addEventListener('click', async () => {
    const url = importUrlEl.value.trim();
    if (!url) {
      showNotice('Enter a public job URL first.');
      return;
    }
    importUrlBtn.disabled = true;
    importStatus.textContent = 'Inspecting public URL...';
    fallbackBox.style.display = 'none';
    try {
      const result = await postJson('/api/pipeline/jobs/import-url', { url, save: true });
      if (result.manual_fallback) {
        pendingFallbackUrl = result.url || url;
        fallbackReason.textContent = result.reason || 'Paste the job description manually.';
        fallbackTitle.value = '';
        fallbackCompany.value = '';
        fallbackDesc.value = '';
        fallbackBox.style.display = 'block';
        importStatus.textContent = `Manual paste fallback opened (${result.ats_family || 'unknown'}).`;
        showNotice('Blocked or login-gated URL — paste JD manually below.');
        return;
      }
      const job = result.job || {};
      importStatus.textContent = `Imported "${job.title || 'Job'}" via ${result.extraction} (${job.ats_family || 'unknown'}).`;
      if (typeof reload === 'function') await reload();
      await renderPreflightBoard();
      showNotice(`Imported job (${result.extraction}).`);
    } catch (err) {
      importStatus.textContent = err.message;
      showNotice(err.message);
    } finally {
      importUrlBtn.disabled = false;
    }
  });

  fallbackCancelBtn.addEventListener('click', () => {
    fallbackBox.style.display = 'none';
    pendingFallbackUrl = '';
  });

  fallbackSaveBtn.addEventListener('click', async () => {
    const targetUrl = pendingFallbackUrl || importUrlEl.value.trim();
    fallbackSaveBtn.disabled = true;
    try {
      const result = await postJson('/api/pipeline/jobs/import-url', {
        url: targetUrl,
        manual_paste: true,
        title: fallbackTitle.value.trim(),
        company: fallbackCompany.value.trim(),
        description: fallbackDesc.value.trim(),
      });
      fallbackBox.style.display = 'none';
      pendingFallbackUrl = '';
      const job = result.job || {};
      importStatus.textContent = `Saved manually pasted job "${job.title || 'Job'}" (${job.ats_family || 'unknown'}).`;
      if (typeof reload === 'function') await reload();
      await renderPreflightBoard();
      showNotice('Saved pasted job + D1 Pre-Flight.');
    } catch (err) {
      importStatus.textContent = err.message;
      showNotice(err.message);
    } finally {
      fallbackSaveBtn.disabled = false;
    }
  });

  preflightAllBtn.addEventListener('click', async () => {
    preflightAllBtn.disabled = true;
    try {
      const result = await postJson('/api/pipeline/jobs/preflight-all', {});
      if (typeof reload === 'function') await reload();
      await renderPreflightBoard();
      showNotice(`D1 Pre-Flight updated for ${result.evaluated_count} jobs.`);
    } catch (err) {
      showNotice(err.message);
    } finally {
      preflightAllBtn.disabled = false;
    }
  });

  preflightBoard.addEventListener('click', async (event) => {
    const btn = event.target.closest('button[data-preflight-job-id]');
    if (!btn) return;
    const jobId = btn.getAttribute('data-preflight-job-id');
    btn.disabled = true;
    try {
      await postJson(`/api/pipeline/jobs/${encodeURIComponent(jobId)}/preflight`, {});
      if (typeof reload === 'function') await reload();
      await renderPreflightBoard();
      showNotice(`D1 Pre-Flight refreshed for job #${jobId}.`);
    } catch (err) {
      showNotice(err.message);
    } finally {
      btn.disabled = false;
    }
  });

  refreshPipelineStatus();
  renderPreflightBoard();
})();
