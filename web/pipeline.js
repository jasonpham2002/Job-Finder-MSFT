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
    <div style="border-top:1px solid #d9e1ea;padding-top:10px;margin-top:12px;">
      <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;">
        <div>
          <strong>D2 Voice-Preserving Anti-Slop Tailor &amp; Workday Preview (A-04)</strong>
          <span id="pipelineTailorBadge"></span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
          <select id="pipelineTailorMode" aria-label="Tailor mode" style="width:auto;min-width:170px;">
            <option value="auto">Mode: Auto (LLM if configured)</option>
            <option value="llm">Mode: LLM Only</option>
            <option value="heuristic">Mode: Deterministic Offline</option>
          </select>
          <button id="pipelineAiTailorBtn" type="button">Run AI Anti-Slop Tailor (Selected Job)</button>
          <button id="pipelineRelintBtn" type="button" class="secondary">Re-Lint Draft &amp; Workday Preview</button>
          <button id="pipelineExportDocxBtn" type="button" class="secondary">Download ATS-Clean .docx</button>
        </div>
      </div>
      <div id="pipelineTailorStatus" class="muted" style="margin-top:6px;">Select a job, then run Anti-Slop Tailor to verify every claim against your resume and preview clean OOXML text.</div>
      <div id="pipelineTailorWorkspace" style="margin-top:10px;"></div>
    </div>
    <div style="border-top:1px solid #d9e1ea;padding-top:10px;margin-top:12px;">
      <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;">
        <div>
          <strong>D5 Gap-to-Proof Bridge &amp; D2 Callback Cheat Sheet (A-05)</strong>
          <span id="pipelineGapBadge"></span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
          <select id="pipelineGapMode" aria-label="Gap analysis mode" style="width:auto;min-width:170px;">
            <option value="auto">Mode: Auto (LLM if configured)</option>
            <option value="llm">Mode: LLM Only</option>
            <option value="heuristic">Mode: Deterministic Offline</option>
          </select>
          <button id="pipelineAnalyzeGapsBtn" type="button">Analyze Skill Gaps (Selected Job)</button>
          <button id="pipelineRefreshCallbackBtn" type="button" class="secondary">Refresh Callback Cheat Sheet</button>
        </div>
      </div>
      <div id="pipelineGapStatus" class="muted" style="margin-top:6px;">Classify wording gaps vs. true skill gaps (blocked until a public proof URL is verified) and preview your 30-second interview callback sheet.</div>
      <div id="pipelineGapWorkspace" style="margin-top:10px;"></div>
      <div id="pipelineCallbackWorkspace" style="margin-top:10px;"></div>
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
  const tailorModeEl = document.getElementById('pipelineTailorMode');
  const aiTailorBtn = document.getElementById('pipelineAiTailorBtn');
  const relintBtn = document.getElementById('pipelineRelintBtn');
  const exportDocxBtn = document.getElementById('pipelineExportDocxBtn');
  const tailorStatusEl = document.getElementById('pipelineTailorStatus');
  const tailorWorkspaceEl = document.getElementById('pipelineTailorWorkspace');
  const gapModeEl = document.getElementById('pipelineGapMode');
  const analyzeGapsBtn = document.getElementById('pipelineAnalyzeGapsBtn');
  const refreshCallbackBtn = document.getElementById('pipelineRefreshCallbackBtn');
  const gapBadgeEl = document.getElementById('pipelineGapBadge');
  const gapStatusEl = document.getElementById('pipelineGapStatus');
  const gapWorkspaceEl = document.getElementById('pipelineGapWorkspace');
  const callbackWorkspaceEl = document.getElementById('pipelineCallbackWorkspace');

  let pendingFallbackUrl = '';
  let activeCopilotAppId = null;
  let activeTailorAppId = null;
  let lastTailorReport = null;

  function renderGapReport(data) {
    if (!gapWorkspaceEl) return;
    if (!data) {
      if (gapBadgeEl) gapBadgeEl.innerHTML = '';
      gapWorkspaceEl.innerHTML = '<div class="small muted">Select a job and click "Analyze Skill Gaps" to classify wording gaps vs. unverified skills needing a 48h micro-project proof URL.</div>';
      return;
    }
    const wording = Array.isArray(data.wording_gaps) ? data.wording_gaps : [];
    const skills = Array.isArray(data.skill_gaps) ? data.skill_gaps : [];
    const verifiedCount = skills.filter((s) => Boolean(s.verified)).length;
    if (gapBadgeEl) {
      gapBadgeEl.innerHTML = badgeHtml(`Wording: ${wording.length}`, 'neutral')
        + badgeHtml(`Skill Gaps: ${skills.length}`, skills.length ? 'warn' : 'good')
        + badgeHtml(`Verified Proofs: ${verifiedCount}`, verifiedCount ? 'good' : 'neutral');
    }

    const wordingHtml = wording.length
      ? wording.map((w) => `
          <div style="border:1px solid #d5eadc;background:#f4fbf6;padding:6px 8px;border-radius:6px;margin-bottom:6px;">
            <div class="small"><strong>Job Term:</strong> ${esc(w.job_term)}</div>
            <div class="small muted"><strong>Candidate Evidence:</strong> ${esc(w.candidate_evidence)}</div>
          </div>
        `).join('')
      : '<div class="small muted">No synonym/wording gaps detected for this role.</div>';

    const skillsHtml = skills.length
      ? skills.map((s) => {
          const isVerified = Boolean(s.verified);
          const safeUrl = s.proof_url && /^https?:\/\//i.test(String(s.proof_url)) ? String(s.proof_url) : '';
          const statusChip = isVerified
            ? badgeHtml('Verified & Unlocked for Tailor', 'good')
            : badgeHtml('Blocked Until Verified', 'bad');
          const proofDisplay = safeUrl
            ? `<div class="small" style="margin-top:4px;"><strong>Verified Proof:</strong> <a href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(safeUrl)}</a></div>`
            : '';
          const verifyControls = s.id
            ? `
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;">
                <input id="pipelineProofUrl_${Number(s.id)}" type="url" value="${esc(safeUrl)}" placeholder="https://github.com/you/micro-proof" style="flex:1;min-width:190px;" />
                <button type="button" data-verify-gap-id="${Number(s.id)}" class="${isVerified ? 'secondary' : ''}">${isVerified ? 'Update Proof URL' : 'Verify Proof & Unlock'}</button>
              </div>
            `
            : '';
          return `
            <div style="border:1px solid ${isVerified ? '#b7e1c4' : '#f1c7c2'};background:${isVerified ? '#f4fbf6' : '#fff8f7'};padding:6px 8px;border-radius:6px;margin-bottom:6px;">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;">
                <strong>${esc(s.skill_name)}</strong>
                ${statusChip}
              </div>
              <div class="small" style="margin-top:4px;"><strong>48h Micro-Project Brief:</strong> ${esc(s.micro_project_brief)}</div>
              ${proofDisplay}
              ${verifyControls}
            </div>
          `;
        }).join('')
      : '<div class="small muted">No missing true skills detected against current job keywords.</div>';

    gapWorkspaceEl.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div style="border:1px solid #d9e1ea;border-radius:8px;padding:8px;background:#fff;">
          <div style="font-weight:600;margin-bottom:6px;">Wording Gaps (Rephrasing OK) (${wording.length})</div>
          ${wordingHtml}
        </div>
        <div style="border:1px solid #d9e1ea;border-radius:8px;padding:8px;background:#fff;">
          <div style="font-weight:600;margin-bottom:6px;">True Skill Gaps (Blocked Without Public Proof) (${skills.length})</div>
          ${skillsHtml}
        </div>
      </div>
    `;
  }

  function renderCallbackCheatSheet(appId, cb, isImmutable) {
    if (!callbackWorkspaceEl) return;
    if (!cb || typeof cb !== 'object' || Object.keys(cb).length === 0) {
      callbackWorkspaceEl.innerHTML = '<div class="small muted">Prepare Anti-Slop Tailor, Co-Pilot, or click "Refresh Callback Cheat Sheet" to generate a 30-second recruiter callback brief.</div>';
      return;
    }
    const diffs = Array.isArray(cb.diff_summary) ? cb.diff_summary : [];
    const answers = (cb.submitted_answers && typeof cb.submitted_answers === 'object') ? cb.submitted_answers : {};
    const answerEntries = Object.entries(answers).filter(([, val]) => val !== null && val !== undefined && String(val).trim() !== '');
    const proofs = Array.isArray(cb.verified_gap_proofs) ? cb.verified_gap_proofs : [];
    const probes = Array.isArray(cb.probe_questions) ? cb.probe_questions : [];

    const diffHtml = diffs.length
      ? diffs.map((d) => `<li class="small"><strong>${esc(d.change_type || 'edit')}:</strong> ${esc(d.summary || d.edited || d.original)}</li>`).join('')
      : '<li class="small muted">Matches master resume baseline cleanly.</li>';

    const answersHtml = answerEntries.length
      ? answerEntries.map(([k, v]) => `<div class="small"><strong>${esc(k)}:</strong> ${esc(String(v))}</div>`).join('')
      : '<div class="small muted">No candidate application answers saved yet.</div>';

    const proofsHtml = proofs.length
      ? proofs.map((p) => {
          const safeUrl = p.proof_url && /^https?:\/\//i.test(String(p.proof_url)) ? String(p.proof_url) : '';
          const link = safeUrl
            ? ` — <a href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(safeUrl)}</a>`
            : '';
          return `<li class="small"><strong>${esc(p.skill_name)}</strong>${link}</li>`;
        }).join('')
      : '<li class="small muted">No verified gap proofs attached for this role yet.</li>';

    const probesHtml = probes.length
      ? probes.map((q) => `<li class="small">${esc(q)}</li>`).join('')
      : '<li class="small muted">Run Refresh Callback Cheat Sheet to generate 3 interviewer probe questions.</li>';

    const metaBadges = [
      appId ? badgeHtml(`App #${appId}`, 'neutral') : '',
      isImmutable ? badgeHtml('Confirmed Receipt (Immutable)', 'good') : '',
      cb.confirmation_reference ? badgeHtml(`Ref: ${cb.confirmation_reference}`, 'good') : '',
      cb.callback_generation_mode ? badgeHtml(`Callback: ${cb.callback_generation_mode}`, 'neutral') : '',
    ].join('');

    callbackWorkspaceEl.innerHTML = `
      <div style="border:1px solid #d9e1ea;border-radius:8px;padding:10px;background:#fff;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
          <strong>D2 30-Second Callback Cheat Sheet Snapshot</strong>
          <div>${metaBadges}</div>
        </div>
        <div class="small" style="margin-bottom:6px;"><strong>Why This Role:</strong> ${esc(cb.why_this_role || 'Tailor or build Co-Pilot packet to populate role pitch.')}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:6px;">
          <div style="border:1px solid #e6ecf2;border-radius:6px;padding:6px 8px;background:#fafcff;">
            <div class="small" style="font-weight:600;margin-bottom:4px;">Master -&gt; Tailored Diff Summary (${diffs.length})</div>
            <ul style="margin:0 0 0 16px;padding:0;">${diffHtml}</ul>
          </div>
          <div style="border:1px solid #e6ecf2;border-radius:6px;padding:6px 8px;background:#fafcff;">
            <div class="small" style="font-weight:600;margin-bottom:4px;">Submitted Application Answers</div>
            ${answersHtml}
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;">
          <div style="border:1px solid #e6ecf2;border-radius:6px;padding:6px 8px;background:#fafcff;">
            <div class="small" style="font-weight:600;margin-bottom:4px;">Verified Gap Proofs (${proofs.length})</div>
            <ul style="margin:0 0 0 16px;padding:0;">${proofsHtml}</ul>
          </div>
          <div style="border:1px solid #e6ecf2;border-radius:6px;padding:6px 8px;background:#fafcff;">
            <div class="small" style="font-weight:600;margin-bottom:4px;">3 Likely Interviewer Probe Questions</div>
            <ol style="margin:0 0 0 16px;padding:0;">${probesHtml}</ol>
          </div>
        </div>
      </div>
    `;
  }

  async function renderGapBoardForSelectedJob() {
    if (!gapWorkspaceEl) return;
    if (typeof chosen === 'undefined' || !chosen || !chosen.id) {
      renderGapReport(null);
      return;
    }
    try {
      const resp = await fetch(`/api/pipeline/jobs/${Number(chosen.id)}/gaps`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Could not load gap analysis');
      if (data.wording_gaps.length || data.skill_gaps.length) {
        renderGapReport(data);
        if (gapStatusEl) {
          gapStatusEl.textContent = `Loaded ${data.wording_gaps.length} wording gaps and ${data.skill_gaps.length} true skill gaps (${data.verified_count} verified proofs unlocked).`;
        }
      } else {
        renderGapReport(null);
      }
    } catch (_err) {
      renderGapReport(null);
    }
  }

  function base64ToUint8Array(b64) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  function renderTailorReport(report) {
    if (!tailorWorkspaceEl) return;
    if (!report) {
      tailorWorkspaceEl.innerHTML = '';
      return;
    }
    const claims = Array.isArray(report.claim_evidence_map) ? report.claim_evidence_map : [];
    const changes = Array.isArray(report.changes) ? report.changes : [];
    const slopWarnings = Array.isArray(report.slop_warnings) ? report.slop_warnings : [];
    const flaggedTerms = Array.isArray(report.flagged_terms) ? report.flagged_terms : [];
    const unverified = Array.isArray(report.unverified_claims) ? report.unverified_claims : [];
    const questions = Array.isArray(report.questions_for_candidate) ? report.questions_for_candidate : [];
    const diagWarnings = (report.ats_diagnostics && Array.isArray(report.ats_diagnostics.warnings))
      ? report.ats_diagnostics.warnings
      : [];
    const fitBefore = report.fit_before && typeof report.fit_before.fit_score === 'number'
      ? report.fit_before.fit_score
      : null;
    const fitAfter = report.fit_after && typeof report.fit_after.fit_score === 'number'
      ? report.fit_after.fit_score
      : (report.fit_match && typeof report.fit_match.fit_score === 'number' ? report.fit_match.fit_score : null);

    const modeLabel = report.generation_mode
      ? `${report.generation_mode}${report.provider ? ` (${report.provider}:${report.model || ''})` : ''}`
      : 'lint_check';
    const slopTone = slopWarnings.length === 0 ? 'good' : 'warn';
    const unverifiedTone = unverified.length === 0 ? 'good' : 'danger';
    const diagTone = diagWarnings.length === 0 ? 'good' : 'warn';

    const fitBadge = fitAfter !== null
      ? badgeHtml(
          fitBefore !== null ? `ATS Fit: ${fitBefore}% -> ${fitAfter}%` : `ATS Fit: ${fitAfter}%`,
          fitAfter >= 65 ? 'good' : 'warn',
        )
      : '';

    const badges = [
      badgeHtml(`Mode: ${modeLabel}`, report.generation_mode === 'llm' ? 'good' : 'neutral'),
      fitBadge,
      badgeHtml(`Grounded Claims: ${claims.length}`, claims.length > 0 ? 'good' : 'warn'),
      badgeHtml(`Unverified: ${unverified.length}`, unverifiedTone),
      badgeHtml(`Slop Warnings: ${slopWarnings.length}`, slopTone),
      badgeHtml(`Workday Layout Warnings: ${diagWarnings.length}`, diagTone),
    ].join('');

    const changesHtml = changes.length
      ? changes.map((c) => (
          `<div style="border-bottom:1px solid #eef2f7;padding:5px 0;">
            <div><strong>Orig:</strong> <span class="muted">${esc(c.original || '(new)')}</span></div>
            <div><strong>Edit:</strong> ${esc(c.edited || '')}</div>
            ${c.reason ? `<div class="muted" style="font-size:11px;">Reason: ${esc(c.reason)}</div>` : ''}
          </div>`
        )).join('')
      : '<div class="muted">No structural edits logged in this snapshot.</div>';

    const claimsHtml = claims.length
      ? `<table style="width:100%;border-collapse:collapse;font-size:12px;">
          <thead>
            <tr style="text-align:left;border-bottom:1px solid #d9e1ea;">
              <th style="padding:4px;">Tailored Claim</th>
              <th style="padding:4px;">Source Resume Evidence</th>
            </tr>
          </thead>
          <tbody>
            ${claims.map((item) => (
              `<tr style="border-bottom:1px solid #eef2f7;">
                <td style="padding:4px;vertical-align:top;">${esc(item.claim || '')}</td>
                <td style="padding:4px;vertical-align:top;color:#116337;">${esc(item.source_snippet || '')}</td>
              </tr>`
            )).join('')}
          </tbody>
        </table>`
      : '<div class="muted">No claim trace entries available for this draft.</div>';

    const unverifiedHtml = (unverified.length || questions.length)
      ? `<div style="border:1px solid ${unverified.length ? '#f5aaaa' : '#f0cc7a'};background:${unverified.length ? '#fdecec' : '#fff6e0'};border-radius:6px;padding:8px;margin-top:8px;">
          ${unverified.length ? `<div><strong>Unverified Claims Flagged (${unverified.length}):</strong><ul style="margin:4px 0 6px 18px;">${unverified.map((u) => `<li>${esc(u)}</li>`).join('')}</ul></div>` : ''}
          ${questions.length ? `<div><strong>Questions for Candidate Before Accepting:</strong><ul style="margin:4px 0 0 18px;">${questions.map((q) => `<li>${esc(q)}</li>`).join('')}</ul></div>` : ''}
        </div>`
      : '';

    const slopHtml = slopWarnings.length
      ? `<ul style="margin:4px 0 0 18px;color:#8a5200;">
          ${slopWarnings.map((w) => `<li>${esc(w)}</li>`).join('')}
         </ul>
         ${flaggedTerms.length ? `<div class="muted" style="font-size:11px;margin-top:4px;">Flagged terms: ${esc(flaggedTerms.map((ft) => (typeof ft === 'string' ? ft : `${ft.term} (${ft.suggestion || 'rewrite plainly'})`)).join('; '))}</div>` : ''}`
      : '<div style="color:#116337;">Clean — zero AI slop buzzwords or canned hype patterns detected.</div>';

    const workdayWarningsHtml = diagWarnings.length
      ? `<ul style="margin:4px 0 6px 18px;color:#8a5200;">${diagWarnings.map((w) => `<li>${esc(w)}</li>`).join('')}</ul>`
      : '<div style="color:#116337;margin-bottom:4px;">Single-column OOXML linearized cleanly with zero Workday layout warnings.</div>';

    tailorWorkspaceEl.innerHTML = `
      <div style="margin-bottom:8px;">${badges}</div>
      ${report.why_this_role ? `<div style="background:#f8fafc;border:1px solid #d9e1ea;border-radius:6px;padding:8px;margin-bottom:8px;"><strong>Why This Role (Callback Hook):</strong> ${esc(report.why_this_role)}</div>` : ''}
      ${unverifiedHtml}
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;margin-top:8px;">
        <div style="border:1px solid #d9e1ea;border-radius:6px;padding:8px;background:#fff;">
          <strong>Claim Trace (Claim &rarr; Source Snippet)</strong>
          <div style="max-height:200px;overflow:auto;margin-top:4px;">${claimsHtml}</div>
        </div>
        <div style="border:1px solid #d9e1ea;border-radius:6px;padding:8px;background:#fff;">
          <strong>Change Diff &amp; Voice Audit</strong>
          <div style="max-height:150px;overflow:auto;margin-top:4px;">${changesHtml}</div>
          <div style="border-top:1px solid #eef2f7;margin-top:6px;padding-top:6px;">
            <strong>Anti-Slop Lint (Score: ${esc(report.slop_score ?? 0)})</strong>
            ${slopHtml}
          </div>
        </div>
      </div>
      <div style="border:1px solid #d9e1ea;border-radius:6px;padding:8px;background:#f8fafc;margin-top:8px;">
        <strong>See What Workday Sees (Plain-Text .docx Round-Trip)</strong>
        ${workdayWarningsHtml}
        <pre style="margin:0;white-space:pre-wrap;font-size:11px;max-height:160px;overflow:auto;background:#fff;padding:6px;border:1px solid #e2e8f0;border-radius:4px;">${esc(report.ats_preview_text || '')}</pre>
        ${report.resume_sha256 ? `<div class="muted" style="font-size:11px;margin-top:4px;">SHA-256: <code>${esc(report.resume_sha256)}</code></div>` : ''}
      </div>
    `;
  }

  async function syncTailorWorkspaceForSelectedJob() {
    renderGapBoardForSelectedJob();
    if (!tailorWorkspaceEl) return;
    if (typeof chosen === 'undefined' || !chosen || !chosen.id) {
      activeTailorAppId = null;
      renderCallbackCheatSheet(null, null, false);
      return;
    }
    try {
      const resp = await fetch('/api/state');
      const stateData = await resp.json();
      const apps = Array.isArray(stateData.applications) ? stateData.applications : [];
      const matching = apps.filter((a) => Number(a.job_id) === Number(chosen.id) && a.status !== 'test_submitted');
      const latest = matching[0] || null;
      if (!latest) {
        activeTailorAppId = null;
        renderTailorReport(null);
        renderCallbackCheatSheet(null, null, false);
        return;
      }
      activeTailorAppId = latest.id;
      const claims = safeParseJson(latest.claim_map_json) || [];
      const slopWarnings = safeParseJson(latest.slop_warnings_json) || [];
      const cb = safeParseJson(latest.callback_packet_json) || {};
      const tailorSummary = cb.tailor_summary || {};
      if (claims.length || latest.ats_preview_text || slopWarnings.length) {
        lastTailorReport = {
          claim_evidence_map: claims,
          slop_warnings: slopWarnings,
          flagged_terms: [],
          slop_score: tailorSummary.slop_score ?? slopWarnings.length * 25,
          unverified_claims: [],
          questions_for_candidate: [],
          ats_preview_text: latest.ats_preview_text || '',
          ats_diagnostics: { warnings: [] },
          changes: cb.tailor_changes || [],
          why_this_role: cb.why_this_role || '',
          generation_mode: tailorSummary.generation_mode || '',
          provider: tailorSummary.provider || '',
          model: tailorSummary.model || '',
          resume_sha256: latest.resume_sha256 || '',
          fit_after: { fit_score: latest.fit_score },
        };
        renderTailorReport(lastTailorReport);
      } else {
        renderTailorReport(null);
      }
      if (Array.isArray(cb.probe_questions) && Array.isArray(cb.diff_summary)) {
        renderCallbackCheatSheet(latest.id, cb, latest.status === 'confirmed');
      } else {
        const cbResp = await fetch(`/api/pipeline/applications/${Number(latest.id)}/callback-packet`);
        const cbData = await cbResp.json();
        if (cbResp.ok && cbData.callback_packet) {
          renderCallbackCheatSheet(latest.id, cbData.callback_packet, Boolean(cbData.immutable));
        } else {
          renderCallbackCheatSheet(latest.id, cb, latest.status === 'confirmed');
        }
      }
    } catch (_err) {
      // Non-blocking UI sync
    }
  }

  async function refreshPipelineStatus() {
    try {
      const resp = await fetch('/api/pipeline/status');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Status check failed');
      const m = data.model_adapter || {};
      const d = data.discovery_adapter || {};
      const a = data.application_adapter || {};
      const g = data.gap_bridge_adapter || {};
      const llmLabel = m.configured
        ? `LLM: ${m.active_provider} (${m.active_model})`
        : 'LLM: offline';
      const serperLabel = d.serper_configured ? 'Serper: ready' : 'Serper: ATS-only';
      const copilotLabel = a.requires_explicit_approval ? 'D3 Co-Pilot: ready' : 'D3: pending';
      const gapLabel = g.implemented ? 'D5: ready' : 'D5: pending';
      statusPill.textContent = `${llmLabel} | ${serperLabel} | ${copilotLabel} | ${gapLabel}`;
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
    const cbData = appObj.callback_packet || safeParseJson(appObj.callback_packet_json);
    if (cbData) {
      renderCallbackCheatSheet(appObj.id, cbData, appObj.status === 'confirmed');
    }
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
      if (result.application && result.application.callback_packet) {
        renderCallbackCheatSheet(
          result.application.id,
          result.application.callback_packet,
          result.application.status === 'confirmed'
        );
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

  if (aiTailorBtn) {
    aiTailorBtn.addEventListener('click', async () => {
      if (typeof chosen === 'undefined' || !chosen || !chosen.id) {
        showNotice('Select a job from the list before running Anti-Slop Tailor.');
        return;
      }
      const mode = tailorModeEl ? tailorModeEl.value : 'auto';
      if (tailorStatusEl) {
        tailorStatusEl.textContent = `Running D2 Anti-Slop Tailor (${mode}) for ${chosen.company} — ${chosen.title}...`;
      }
      aiTailorBtn.disabled = true;
      try {
        const data = await postJson('/api/pipeline/prepare-ai', {
          job_id: chosen.id,
          mode,
        });
        activeTailorAppId = data.application ? data.application.id : null;
        if (activeTailorAppId) {
          activeCopilotAppId = activeTailorAppId;
        }
        lastTailorReport = data;
        const tailoredBox = document.getElementById('tailored');
        if (tailoredBox) tailoredBox.value = data.tailored_text || '';
        const fitBox = document.getElementById('fit');
        if (fitBox && data.fit_after) {
          fitBox.innerHTML = `<span class="badge">Fit ${esc(data.fit_after.fit_score)}%</span>`
            + `<span class="muted"> Matched: ${esc((data.fit_after.matched || []).join(', ') || 'none')} | Missing: ${esc((data.fit_after.missing || []).join(', ') || 'none')}</span>`;
        }
        if (tailorStatusEl) {
          tailorStatusEl.textContent = `Tailored via ${data.generation_mode} (Application #${activeTailorAppId || '?'}; ${data.claim_evidence_map.length} verified claims, ${data.slop_warnings.length} slop warnings).`;
        }
        renderTailorReport(data);
        if (data.application && data.application.callback_packet) {
          renderCallbackCheatSheet(
            data.application.id,
            data.application.callback_packet,
            data.application.status === 'confirmed'
          );
        }
        showNotice('AI Anti-Slop Tailor completed with verified claim trace.');
        if (typeof reload === 'function') await reload();
        await renderReceiptLedger();
      } catch (err) {
        if (tailorStatusEl) tailorStatusEl.textContent = `Error: ${err.message}`;
        showNotice(`Anti-Slop Tailor failed: ${err.message}`);
      } finally {
        aiTailorBtn.disabled = false;
      }
    });
  }

  if (relintBtn) {
    relintBtn.addEventListener('click', async () => {
      const tailoredBox = document.getElementById('tailored');
      const text = tailoredBox ? tailoredBox.value.trim() : '';
      if (!text) {
        showNotice('Tailored resume editor is empty; paste or generate a draft first.');
        return;
      }
      relintBtn.disabled = true;
      try {
        const data = await postJson('/api/pipeline/tailor/lint', {
          text,
          job_id: (typeof chosen !== 'undefined' && chosen && chosen.id) ? chosen.id : undefined,
          application_id: activeTailorAppId || undefined,
          save: Boolean(activeTailorAppId),
          claim_evidence_map: lastTailorReport ? lastTailorReport.claim_evidence_map : undefined,
        });
        const merged = {
          ...(lastTailorReport || {}),
          slop_warnings: data.slop_warnings,
          flagged_terms: data.flagged_terms,
          slop_score: data.slop_score,
          ats_preview_text: data.ats_preview_text,
          ats_diagnostics: data.ats_diagnostics,
          resume_sha256: data.resume_sha256,
          fit_match: data.fit_match,
        };
        if (data.grounding) {
          merged.claim_evidence_map = data.grounding.claim_evidence_map;
          merged.unverified_claims = data.grounding.unverified_claims;
          merged.questions_for_candidate = data.grounding.questions_for_candidate;
        }
        lastTailorReport = merged;
        renderTailorReport(merged);
        if (tailorStatusEl) {
          tailorStatusEl.textContent = `Re-linted draft: ${data.slop_warnings.length} slop warnings, Workday preview updated.`;
        }
        showNotice('Re-lint & Workday preview refreshed.');
      } catch (err) {
        if (tailorStatusEl) tailorStatusEl.textContent = `Re-lint failed: ${err.message}`;
        showNotice(`Re-lint error: ${err.message}`);
      } finally {
        relintBtn.disabled = false;
      }
    });
  }

  if (exportDocxBtn) {
    exportDocxBtn.addEventListener('click', async () => {
      const targetAppId = activeTailorAppId || activeCopilotAppId;
      if (!targetAppId) {
        showNotice('Run AI Anti-Slop Tailor (or Prepare Co-Pilot Packet) first to create a draft application.');
        return;
      }
      const tailoredBox = document.getElementById('tailored');
      const currentText = tailoredBox ? tailoredBox.value.trim() : '';
      exportDocxBtn.disabled = true;
      try {
        const data = await postJson(`/api/pipeline/applications/${targetAppId}/export-docx`, {
          text: currentText || undefined,
        });
        const bytes = base64ToUint8Array(data.content_base64);
        const blob = new Blob([bytes], { type: data.mime_type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename || `application_${targetAppId}_tailored.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        if (tailorStatusEl) {
          tailorStatusEl.textContent = `Downloaded ${data.filename} (${data.byte_length} bytes, SHA-256 ${data.docx_sha256.slice(0, 12)}...).`;
        }
        showNotice(`Exported ATS-clean DOCX: ${data.filename}`);
      } catch (err) {
        showNotice(`DOCX export failed: ${err.message}`);
      } finally {
        exportDocxBtn.disabled = false;
      }
    });
  }

  if (analyzeGapsBtn) {
    analyzeGapsBtn.addEventListener('click', async () => {
      if (typeof chosen === 'undefined' || !chosen || !chosen.id) {
        showNotice('Select a job from the list before analyzing skill gaps.');
        return;
      }
      const mode = gapModeEl ? gapModeEl.value : 'auto';
      if (gapStatusEl) {
        gapStatusEl.textContent = `Running D5 Gap-to-Proof analysis (${mode}) for ${chosen.company} — ${chosen.title}...`;
      }
      analyzeGapsBtn.disabled = true;
      try {
        const data = await postJson('/api/pipeline/gaps/analyze', {
          job_id: chosen.id,
          mode,
        });
        renderGapReport(data);
        if (gapStatusEl) {
          gapStatusEl.textContent = `Analyzed via ${data.generation_mode}: ${data.wording_gaps.length} wording gaps, ${data.skill_gaps.length} true skill gaps (${data.verified_count} verified).`;
        }
        showNotice('D5 Gap-to-Proof analysis complete.');
        await syncTailorWorkspaceForSelectedJob();
      } catch (err) {
        if (gapStatusEl) gapStatusEl.textContent = `Gap analysis error: ${err.message}`;
        showNotice(`Gap analysis failed: ${err.message}`);
      } finally {
        analyzeGapsBtn.disabled = false;
      }
    });
  }

  if (gapWorkspaceEl) {
    gapWorkspaceEl.addEventListener('click', async (evt) => {
      const btn = evt.target && evt.target.closest ? evt.target.closest('[data-verify-gap-id]') : null;
      if (!btn) return;
      const gapId = Number(btn.getAttribute('data-verify-gap-id'));
      const inputEl = document.getElementById(`pipelineProofUrl_${gapId}`);
      const proofUrl = inputEl ? inputEl.value.trim() : '';
      if (!proofUrl) {
        showNotice('Enter a public https:// proof URL (e.g., GitHub repo or live demo) before verifying.');
        return;
      }
      btn.disabled = true;
      try {
        const data = await postJson(`/api/pipeline/gaps/${gapId}/verify`, {
          proof_url: proofUrl,
        });
        renderGapReport(data);
        if (gapStatusEl) {
          gapStatusEl.textContent = `Verified proof for "${data.unlocked_skill}"! Re-run AI Anti-Slop Tailor to include this verified project.`;
        }
        showNotice(`Unlocked skill "${data.unlocked_skill}" for tailoring and updated Callback Cheat Sheet.`);
        await syncTailorWorkspaceForSelectedJob();
      } catch (err) {
        if (gapStatusEl) gapStatusEl.textContent = `Verification blocked: ${err.message}`;
        showNotice(`Proof verification failed: ${err.message}`);
      } finally {
        btn.disabled = false;
      }
    });
  }

  if (refreshCallbackBtn) {
    refreshCallbackBtn.addEventListener('click', async () => {
      const targetAppId = activeTailorAppId || activeCopilotAppId || (copilotAppSelect && copilotAppSelect.value ? Number(copilotAppSelect.value) : null);
      if (!targetAppId) {
        showNotice('Prepare Anti-Slop Tailor or Co-Pilot Packet for a job first to build its Callback Cheat Sheet.');
        return;
      }
      const mode = gapModeEl ? gapModeEl.value : 'heuristic';
      refreshCallbackBtn.disabled = true;
      try {
        const data = await postJson(`/api/pipeline/applications/${Number(targetAppId)}/callback-packet`, {
          mode,
          refresh_probes: true,
        });
        renderCallbackCheatSheet(targetAppId, data.callback_packet, Boolean(data.immutable));
        showNotice(
          data.immutable
            ? `Loaded immutable Callback Cheat Sheet for confirmed application #${targetAppId}.`
            : `Updated D2 Callback Cheat Sheet for application #${targetAppId}.`
        );
      } catch (err) {
        showNotice(`Callback Cheat Sheet error: ${err.message}`);
      } finally {
        refreshCallbackBtn.disabled = false;
      }
    });
  }

  const prepareBtn = document.getElementById('prepare');
  if (prepareBtn) {
    prepareBtn.addEventListener('click', () => {
      setTimeout(() => {
        renderReceiptLedger();
        syncTailorWorkspaceForSelectedJob();
      }, 500);
    });
  }

  const jobsListEl = document.getElementById('jobs');
  if (jobsListEl) {
    jobsListEl.addEventListener('click', () => {
      setTimeout(syncTailorWorkspaceForSelectedJob, 50);
    });
  }

  refreshPipelineStatus();
  renderPreflightBoard();
  renderReceiptLedger();
  syncTailorWorkspaceForSelectedJob();
})();
