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

    <div style="border-top:1px solid rgba(128,128,128,0.22);padding-top:12px;margin-top:12px;">
      <div class="paneltop">
        <strong>A-03 D3 Co-Pilot Packet &amp; SHA-256 Receipts</strong>
        <button id="pipelineCopilotBuildSelectedBtn" type="button">Build Co-Pilot for Selected Job</button>
      </div>
      <p class="small">Stages ordered copy-paste fields per ATS portal, locks sensitive EEO/visa/salary fields behind explicit candidate confirmation, and records tamper-evident SHA-256 receipts only when you supply external confirmation evidence.</p>

      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px;">
        <select id="pipelineCopilotAppSelect" style="flex:1 1 260px;"></select>
        <button id="pipelineCopilotLoadBtn" type="button">Load / Refresh Packet</button>
      </div>
      <p class="small" id="pipelineCopilotStatus">Select a prepared application or click "Build Co-Pilot for Selected Job".</p>

      <div id="pipelineCopilotWorkspace" style="display:none;margin-top:8px;">
        <div id="pipelineCopilotSections"></div>

        <div class="fit" style="margin-top:10px;border-left:4px solid #b45309;">
          <strong>LOCKED Sensitive Eligibility &amp; EEO Gate (AI Never Auto-Fills)</strong>
          <p class="small">Enter or explicitly decline each field yourself before recording any real application.</p>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;margin:8px 0;">
            <label class="small">Work Authorization *<input id="pipelineSensWorkAuth" type="text" placeholder="e.g. Authorized in US without sponsorship"></label>
            <label class="small">Visa Sponsorship *<input id="pipelineSensVisa" type="text" placeholder="e.g. No / Yes (specify)"></label>
            <label class="small">Salary Expectation<input id="pipelineSensSalary" type="text" placeholder="Candidate figure or Negotiable"></label>
            <label class="small">Veteran Status (EEO)<input id="pipelineSensVeteran" type="text" placeholder="e.g. Decline to self-identify"></label>
            <label class="small">Disability Status (EEO)<input id="pipelineSensDisability" type="text" placeholder="e.g. Decline to self-identify"></label>
            <label class="small">References<input id="pipelineSensReferences" type="text" placeholder="Available upon request or verified names"></label>
          </div>

          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;margin-top:8px;">
            <label class="small">Submission Outcome
              <select id="pipelineConfirmOutcome">
                <option value="confirmed">Confirmed (external ATS ID/email receipt)</option>
                <option value="manual_required">Manual Required (CAPTCHA / login pause)</option>
                <option value="unknown">Unknown (unverified portal response)</option>
                <option value="failed">Failed (submission error)</option>
              </select>
            </label>
            <label class="small">External Confirmation Ref / ID<input id="pipelineConfirmRef" type="text" placeholder="e.g. GH-94821-CONF or email ID"></label>
            <label class="small">Evidence Note / Screenshot Path<input id="pipelineConfirmEvidence" type="text" placeholder="e.g. Confirmation email + receipt screenshot"></label>
          </div>

          <div style="margin-top:8px;">
            <label class="small" style="display:block;margin-bottom:4px;">
              <input id="pipelineSensitiveConfirmed" type="checkbox">
              I personally entered/verified all 6 locked sensitive fields above.
            </label>
            <label class="small" style="display:block;margin-bottom:8px;">
              <input id="pipelineConfirmApproval" type="checkbox">
              <span id="pipelineApprovalScopeText">I explicitly approve recording this application receipt for the target URL and resume version.</span>
            </label>
            <button id="pipelineConfirmSubmitBtn" type="button">Record Submission Receipt (SHA-256)</button>
          </div>
        </div>
      </div>

      <div id="pipelineReceiptLedger" style="margin-top:10px;"></div>
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

  const copilotBuildSelectedBtn = document.getElementById('pipelineCopilotBuildSelectedBtn');
  const copilotAppSelect = document.getElementById('pipelineCopilotAppSelect');
  const copilotLoadBtn = document.getElementById('pipelineCopilotLoadBtn');
  const copilotStatus = document.getElementById('pipelineCopilotStatus');
  const copilotWorkspace = document.getElementById('pipelineCopilotWorkspace');
  const copilotSectionsEl = document.getElementById('pipelineCopilotSections');

  const sensWorkAuthEl = document.getElementById('pipelineSensWorkAuth');
  const sensVisaEl = document.getElementById('pipelineSensVisa');
  const sensSalaryEl = document.getElementById('pipelineSensSalary');
  const sensVeteranEl = document.getElementById('pipelineSensVeteran');
  const sensDisabilityEl = document.getElementById('pipelineSensDisability');
  const sensReferencesEl = document.getElementById('pipelineSensReferences');

  const confirmOutcomeEl = document.getElementById('pipelineConfirmOutcome');
  const confirmRefEl = document.getElementById('pipelineConfirmRef');
  const confirmEvidenceEl = document.getElementById('pipelineConfirmEvidence');
  const sensitiveConfirmedEl = document.getElementById('pipelineSensitiveConfirmed');
  const confirmApprovalEl = document.getElementById('pipelineConfirmApproval');
  const approvalScopeText = document.getElementById('pipelineApprovalScopeText');
  const confirmSubmitBtn = document.getElementById('pipelineConfirmSubmitBtn');
  const receiptLedgerEl = document.getElementById('pipelineReceiptLedger');

  let pendingFallbackUrl = '';
  let activeCopilotAppId = null;

  async function refreshPipelineStatus() {
    try {
      const resp = await fetch('/api/pipeline/status');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Status check failed');
      const m = data.model_adapter || {};
      const d = data.discovery_adapter || {};
      const a = data.application_adapter || {};
      const llmLabel = m.configured
        ? `LLM: ${m.active_provider} (${m.active_model})`
        : 'LLM: offline';
      const serperLabel = d.serper_configured ? 'Serper: ready' : 'Serper: ATS-only';
      const copilotLabel = a.requires_explicit_approval ? 'D3 Co-Pilot: ready' : 'D3: pending';
      statusPill.textContent = `${llmLabel} | ${serperLabel} | ${copilotLabel}`;
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

  function renderCopilotPacket(appObj, packet) {
    if (!appObj || !packet) {
      copilotWorkspace.style.display = 'none';
      return;
    }
    activeCopilotAppId = appObj.id;
    const answersData = appObj.answers_data || safeParseJson(appObj.answers_json) || {};
    const savedSensitive = answersData.sensitive_answers || {};

    sensWorkAuthEl.value = savedSensitive.work_authorization || '';
    sensVisaEl.value = savedSensitive.visa_sponsorship || '';
    sensSalaryEl.value = savedSensitive.salary_expectation || '';
    sensVeteranEl.value = savedSensitive.veteran_status || '';
    sensDisabilityEl.value = savedSensitive.disability_status || '';
    sensReferencesEl.value = savedSensitive.references || '';

    sensitiveConfirmedEl.checked = Boolean(answersData.sensitive_fields_confirmed);
    confirmApprovalEl.checked = false;
    confirmRefEl.value = appObj.confirmation && appObj.status === 'confirmed' ? appObj.confirmation : '';
    confirmEvidenceEl.value = appObj.evidence_note || '';

    const sections = Array.isArray(packet.ordered_sections) ? packet.ordered_sections : [];
    const nonLockedHtml = sections
      .filter((sec) => !sec.locked)
      .map((sec) => {
        const fieldsHtml = (sec.fields || []).map((field) => {
          const val = field.value || '';
          const isLong = field.key === 'approved_resume_text' || field.key === 'experience_highlights' || field.key === 'additional_answers' || field.key === 'why_company_and_role';
          const inputHtml = isLong
            ? `<textarea data-copilot-answer="${esc(field.key)}" rows="3" style="width:100%;margin-top:4px;font-size:12px;">${esc(val)}</textarea>`
            : `<input data-copilot-answer="${esc(field.key)}" type="text" value="${esc(val)}" style="width:100%;margin-top:4px;">`;
          return `
            <div style="margin-top:6px;">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <span class="small"><strong>${esc(field.label)}</strong> <span style="opacity:0.75;">(${esc(field.source || 'portal')})</span></span>
                <button type="button" data-copy-field="${esc(field.key)}" style="padding:2px 8px;font-size:11px;">Copy</button>
              </div>
              ${inputHtml}
            </div>
          `;
        }).join('');
        return `
          <div class="fit" style="margin-top:8px;">
            <strong>${esc(sec.title)}</strong>
            ${fieldsHtml}
          </div>
        `;
      }).join('');

    const shaPreview = String(appObj.resume_sha256 || '').slice(0, 12);
    approvalScopeText.textContent = `I explicitly approve recording this application for ${appObj.company || 'Employer'} (${appObj.url || 'URL'}) with resume SHA-256 ${shaPreview || 'pending'}...`;
    copilotSectionsEl.innerHTML = `
      <div class="small" style="margin-bottom:6px;">
        ${badgeHtml(`ATS Order: ${packet.ats_family || 'unknown'}`, 'neutral')}
        ${badgeHtml(`Status: ${appObj.status || 'draft'}`, appObj.status === 'confirmed' ? 'good' : (appObj.status === 'test_submitted' ? 'warn' : 'neutral'))}
        ${appObj.status === 'confirmed' ? badgeHtml('Locked Receipt (Immutable)', 'good') : ''}
      </div>
      ${nonLockedHtml}
    `;
    copilotWorkspace.style.display = 'block';
    copilotStatus.textContent = `Loaded D3 Co-Pilot Packet for App #${appObj.id}: ${appObj.title || ''} @ ${appObj.company || ''}.`;
  }

  async function renderReceiptLedger() {
    try {
      const resp = await fetch('/api/applications');
      const apps = await resp.json();
      if (!Array.isArray(apps) || apps.length === 0) {
        copilotAppSelect.innerHTML = '<option value="">No prepared applications yet</option>';
        receiptLedgerEl.innerHTML = '<p class="small">No application receipts yet. Select a job and build a Co-Pilot Packet above.</p>';
        return;
      }
      const prevVal = copilotAppSelect.value || (activeCopilotAppId ? String(activeCopilotAppId) : '');
      copilotAppSelect.innerHTML = apps.map((a) => (
        `<option value="${esc(a.id)}">App #${esc(a.id)} · ${esc(a.title)} @ ${esc(a.company)} [${esc(a.status)}]</option>`
      )).join('');
      if (prevVal && apps.some((a) => String(a.id) === String(prevVal))) {
        copilotAppSelect.value = prevVal;
      }

      receiptLedgerEl.innerHTML = `
        <strong class="small">Tamper-Evident Application Receipt Ledger (D3)</strong>
        ${apps.map((a) => {
          const tone = a.status === 'confirmed'
            ? 'good'
            : (a.status === 'test_submitted' || a.status === 'manual_required' || a.status === 'unknown' ? 'warn' : (a.status === 'failed' ? 'danger' : 'neutral'));
          const modeLabel = a.status === 'test_submitted'
            ? 'DEMO TEST ONLY (Not Real)'
            : (a.status === 'confirmed' ? `CONFIRMED: ${a.confirmation}` : a.status);
          const shaLine = a.resume_sha256 || a.answers_sha256
            ? `<div class="small" style="font-family:monospace;font-size:11px;margin-top:4px;">resume_sha256=${esc((a.resume_sha256 || '').slice(0, 16))}... | answers_sha256=${esc((a.answers_sha256 || 'pending').slice(0, 16))}...</div>`
            : '';
          const tsLine = a.submitted_at ? `<div class="small">Recorded: ${esc(a.submitted_at)}</div>` : '';
          return `
            <div class="fit" style="margin-top:6px;">
              <div>
                <strong>#${esc(a.id)} ${esc(a.title)}</strong> — ${esc(a.company)}
                ${badgeHtml(modeLabel, tone)}
              </div>
              ${shaLine}
              ${tsLine}
            </div>
          `;
        }).join('')}
      `;
    } catch (err) {
      receiptLedgerEl.innerHTML = `<p class="small">${esc(err.message)}</p>`;
    }
  }

  function collectCandidateAnswersFromDom() {
    const out = {};
    copilotSectionsEl.querySelectorAll('[data-copilot-answer]').forEach((el) => {
      const key = el.getAttribute('data-copilot-answer');
      if (key && key !== 'approved_resume_text' && key !== 'portal_account_note' && key !== 'experience_highlights' && key !== 'matched_skills') {
        out[key] = el.value.trim();
      }
    });
    return out;
  }

  function collectSensitiveAnswersFromDom() {
    return {
      work_authorization: sensWorkAuthEl.value.trim(),
      visa_sponsorship: sensVisaEl.value.trim(),
      salary_expectation: sensSalaryEl.value.trim(),
      veteran_status: sensVeteranEl.value.trim(),
      disability_status: sensDisabilityEl.value.trim(),
      references: sensReferencesEl.value.trim(),
    };
  }

  copilotBuildSelectedBtn.addEventListener('click', async () => {
    const selectedJobId = typeof chosen !== 'undefined' && chosen ? chosen : null;
    if (!selectedJobId) {
      showNotice('Select a job in Panel 3 first.');
      return;
    }
    copilotBuildSelectedBtn.disabled = true;
    try {
      const result = await postJson(`/api/pipeline/jobs/${encodeURIComponent(selectedJobId)}/copilot`, {});
      renderCopilotPacket(result.application, result.copilot_packet);
      if (typeof reload === 'function') await reload();
      await renderReceiptLedger();
      copilotAppSelect.value = String(result.application.id);
      showNotice(`Built D3 Co-Pilot Packet for App #${result.application.id}.`);
    } catch (err) {
      copilotStatus.textContent = err.message;
      showNotice(err.message);
    } finally {
      copilotBuildSelectedBtn.disabled = false;
    }
  });

  copilotLoadBtn.addEventListener('click', async () => {
    const appId = copilotAppSelect.value;
    if (!appId) {
      showNotice('Choose an application first or click Build Co-Pilot for Selected Job.');
      return;
    }
    copilotLoadBtn.disabled = true;
    try {
      const result = await postJson(`/api/pipeline/applications/${encodeURIComponent(appId)}/copilot`, {});
      renderCopilotPacket(result.application, result.copilot_packet);
      await renderReceiptLedger();
      showNotice(`Loaded Co-Pilot Packet for App #${appId}.`);
    } catch (err) {
      copilotStatus.textContent = err.message;
      showNotice(err.message);
    } finally {
      copilotLoadBtn.disabled = false;
    }
  });

  copilotSectionsEl.addEventListener('click', async (event) => {
    const btn = event.target.closest('button[data-copy-field]');
    if (!btn) return;
    const key = btn.getAttribute('data-copy-field');
    const target = copilotSectionsEl.querySelector(`[data-copilot-answer="${CSS.escape(key)}"]`);
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target.value || '');
      showNotice(`Copied ${key} to clipboard.`);
    } catch (_err) {
      showNotice('Clipboard unavailable; select and copy the field text manually.');
    }
  });

  confirmSubmitBtn.addEventListener('click', async () => {
    const appId = activeCopilotAppId || copilotAppSelect.value;
    if (!appId) {
      showNotice('Load a Co-Pilot Packet first.');
      return;
    }
    const resumeField = copilotSectionsEl.querySelector('[data-copilot-answer="approved_resume_text"]');
    confirmSubmitBtn.disabled = true;
    try {
      const result = await postJson(`/api/pipeline/applications/${encodeURIComponent(appId)}/confirm`, {
        explicit_user_approval: confirmApprovalEl.checked,
        sensitive_fields_confirmed: sensitiveConfirmedEl.checked,
        outcome: confirmOutcomeEl.value,
        confirmation_reference: confirmRefEl.value.trim(),
        evidence_note: confirmEvidenceEl.value.trim(),
        approved_resume: resumeField ? resumeField.value.trim() : undefined,
        candidate_answers: collectCandidateAnswersFromDom(),
        sensitive_answers: collectSensitiveAnswersFromDom(),
      });
      if (typeof reload === 'function') await reload();
      await renderReceiptLedger();
      if (result.application && result.application.copilot_packet) {
        renderCopilotPacket(result.application, result.application.copilot_packet);
      }
      const msg = result.real_submitted_counted
        ? `Confirmed real application receipt recorded (${result.receipt.confirmation_reference}).`
        : `Recorded status "${result.receipt.status}" (not counted as real confirmed submission).`;
      copilotStatus.textContent = msg;
      showNotice(msg);
    } catch (err) {
      copilotStatus.textContent = err.message;
      showNotice(err.message);
    } finally {
      confirmSubmitBtn.disabled = false;
    }
  });

  const prepareBtn = document.getElementById('prepare');
  if (prepareBtn) {
    prepareBtn.addEventListener('click', () => {
      setTimeout(renderReceiptLedger, 500);
    });
  }

  refreshPipelineStatus();
  renderPreflightBoard();
  renderReceiptLedger();
})();
