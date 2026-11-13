// Owner B Extension Workspace: D4 Artifact Contact Research, B-01 Outreach Delivery & Approval,
// B-02 Inbox Tracker, and B-04 Cooldown/Opt-Out + D2 30-Second Callback Cheat Sheet Trigger UI.
(function () {
  const mount = document.getElementById('outreachExtensions');
  if (!mount) return;

  let activeStagedDraft = null; // Holds { id, review_token, status, job_url, channel, recipient, subject, body, provider }

  async function api(path, payload) {
    const options = payload !== undefined ? {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    } : {};
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Outreach request failed.');
    return data;
  }

  function currentJobId() {
    if (typeof chosen === 'number' && chosen > 0) return chosen;
    return 1;
  }

  function currentJobSummary() {
    if (typeof jobs !== 'undefined' && Array.isArray(jobs)) {
      const found = jobs.find((j) => j.id === currentJobId());
      if (found) return `#${found.id} · ${found.title} (${found.company} · ${found.origin})`;
    }
    return `Job #${currentJobId()}`;
  }

  // ---------------------------------------------------------------------------
  // 1. D4 Public Contact Research Section
  // ---------------------------------------------------------------------------
  const researchSection = document.createElement('div');
  researchSection.className = 'record';
  researchSection.innerHTML = `
    <div class="paneltop">
      <h3>D4 · Artifact-First Public Contact Research</h3>
      <span class="pill" id="outreachActiveJobBadge">Selected job</span>
    </div>
    <p class="small">
      Extracts explicitly attributed people (JSON-LD <code>schema.org/Person</code>, HTML team bio cards, or blog author metadata)
      from a public employer URL. Never scrapes LinkedIn or guesses unlisted emails.
    </p>
    <form id="outreachResearchForm">
      <div class="twocol">
        <div>
          <label>Target Job ID
            <input id="outreachResearchJobId" name="job" type="number" min="1" required>
          </label>
        </div>
        <div>
          <label>Employer team, about, or blog URL
            <input id="outreachResearchSourceUrl" name="source" type="url" placeholder="https://company.com/about" required>
          </label>
        </div>
      </div>
      <details style="margin: 8px 0;">
        <summary class="small" style="cursor: pointer;">
          Optional: supply verified excerpt from this employer URL (for JS-rendered pages)
        </summary>
        <div class="twocol" style="margin-top: 6px;">
          <div>
            <label>Contact name <input id="outreachManualName" placeholder="e.g. Taylor Morgan"></label>
          </div>
          <div>
            <label>Title / Role <input id="outreachManualRole" placeholder="e.g. Senior Technical Recruiter"></label>
          </div>
        </div>
        <div class="twocol">
          <div>
            <label>Artifact type
              <select id="outreachManualType">
                <option value="team_bio">Team / About Bio</option>
                <option value="blog_post">Engineering / Company Blog</option>
                <option value="github_repo">Public GitHub Repo</option>
                <option value="talk">Conference Talk</option>
              </select>
            </label>
          </div>
          <div>
            <label>Published email on page (optional, never guessed)
              <input id="outreachManualEmail" type="email" placeholder="Leave blank unless published">
            </label>
          </div>
        </div>
        <label>Published excerpt / bio snippet from the URL above
          <textarea id="outreachManualSnippet" rows="2" placeholder="Exact quote or bio snippet published on the employer page..."></textarea>
        </label>
      </details>
      <label style="display:flex;align-items:center;gap:6px;margin:8px 0;">
        <input id="outreachResearchConfirmed" name="confirmed" type="checkbox" required>
        I confirm this URL is a public source published by this employer
      </label>
      <button type="submit">Find & Verify Contacts</button>
    </form>
    <div id="outreachContactCards" style="margin-top: 10px;"></div>
  `;

  // ---------------------------------------------------------------------------
  // 2. B-01 Authorized Outreach Delivery & Approval Studio
  // ---------------------------------------------------------------------------
  const deliverySection = document.createElement('div');
  deliverySection.className = 'record';
  deliverySection.style.marginTop = '12px';
  deliverySection.innerHTML = `
    <div class="paneltop">
      <h3>B-01 · Authorized Outreach Delivery & Approval</h3>
      <span class="pill" id="outreachDeliveryBadge">Stage -> Approve -> Send</span>
    </div>
    <p class="small">
      Requires a real (non-fictional) job, an authorized recipient address or LinkedIn profile,
      company cooldown & opt-out firewall clearance, and explicit human approval before sending.
    </p>
    <div class="actions" style="margin-bottom: 8px;">
      <button type="button" id="outreachImportSection5Btn" class="secondary">Load from Section 5 Draft</button>
    </div>
    <div class="twocol">
      <div>
        <label>Job ID <input id="outreachStageJobId" type="number" min="1" required></label>
      </div>
      <div>
        <label>Channel
          <select id="outreachStageChannel">
            <option value="email">Professional Email (Gmail / Outlook / Manual)</option>
            <option value="linkedin">LinkedIn (Manual Copy-Paste Only)</option>
          </select>
        </label>
      </div>
    </div>
    <div class="twocol">
      <div>
        <label>Contact name <input id="outreachStageName" placeholder="Verified contact name"></label>
      </div>
      <div>
        <label>Contact role <input id="outreachStageRole" placeholder="Recruiter / Hiring Manager / Peer"></label>
      </div>
    </div>
    <div class="twocol">
      <div>
        <label>Authorized recipient (Email or https://www.linkedin.com/in/...)
          <input id="outreachStageRecipient" placeholder="recruiter@company.com or https://www.linkedin.com/in/handle">
        </label>
      </div>
      <div>
        <label>Public source URL for contact
          <input id="outreachStageSourceUrl" type="url" placeholder="https://company.com/team">
        </label>
      </div>
    </div>
    <div class="twocol">
      <div>
        <label>Email subject (single line; blank for LinkedIn)
          <input id="outreachStageSubject" placeholder="Question about the role">
        </label>
      </div>
      <div>
        <label>Delivery provider
          <select id="outreachStageProvider">
            <option value="gmail">Gmail OAuth (Primary)</option>
            <option value="outlook">Outlook Contract (Manual Fallback)</option>
            <option value="manual">Manual Copy-Paste</option>
          </select>
        </label>
      </div>
    </div>
    <label>Final outreach message (3 sentences, artifact-anchored, no [YOUR NAME] placeholders)
      <textarea id="outreachStageBody" rows="4" placeholder="Hi ..., I read your bio..."></textarea>
    </label>
    <label style="display:flex;align-items:center;gap:6px;margin:6px 0;">
      <input id="outreachStageAuthRecipient" type="checkbox">
      I confirm the recipient address/profile and source URL are authorized and opted-in
    </label>
    <label style="display:flex;align-items:center;gap:6px;margin:6px 0;">
      <input id="outreachStageExplicitApproval" type="checkbox">
      I have reviewed the exact job URL, recipient, subject, and body and explicitly approve delivery
    </label>
    <div class="actions" style="flex-wrap:wrap;gap:6px;margin-top:8px;">
      <button type="button" id="outreachStageBtn">1 · Stage Delivery Draft</button>
      <button type="button" id="outreachApproveBtn" disabled>2 · Approve Staged Draft</button>
      <button type="button" id="outreachSendBtn" disabled>3 · Send Approved Outreach</button>
      <button type="button" id="outreachManualSentBtn" class="secondary" disabled>4 · Confirm Manually Sent</button>
    </div>
    <div id="outreachDeliveryStatus" class="small" role="status" style="margin-top:8px;"></div>
  `;

  // ---------------------------------------------------------------------------
  // 3. B-02 & B-04 Inbox Tracker + D2 30s Callback Cheat Sheet Drawer
  // ---------------------------------------------------------------------------
  const inboxSection = document.createElement('div');
  inboxSection.className = 'record';
  inboxSection.style.marginTop = '12px';

  const heading = document.createElement('h3');
  heading.textContent = 'B-02 & B-04 · Inbox Tracker & 30s Callback Cheat Sheet';
  const sync = document.createElement('button');
  sync.type = 'button';
  sync.textContent = 'Sync JobFinder-labeled Gmail';
  const simulate = document.createElement('button');
  simulate.type = 'button';
  simulate.className = 'secondary';
  simulate.style.marginLeft = '6px';
  simulate.textContent = 'Test inbox classification (TEST ONLY)';
  const status = document.createElement('p');
  status.className = 'small';
  status.setAttribute('role', 'status');
  const result = document.createElement('ul');
  inboxSection.append(heading, sync, simulate, status, result);

  mount.append(researchSection, deliverySection, inboxSection);

  // Sync active job ID from Section 3 selection
  function syncJobSelection() {
    const jobIdInput = document.getElementById('outreachResearchJobId');
    const stageJobIdInput = document.getElementById('outreachStageJobId');
    const badge = document.getElementById('outreachActiveJobBadge');
    const jid = currentJobId();
    if (jobIdInput && !jobIdInput.value) jobIdInput.value = String(jid);
    if (stageJobIdInput && !stageJobIdInput.value) stageJobIdInput.value = String(jid);
    if (badge) badge.textContent = currentJobSummary();
  }
  syncJobSelection();
  const jobsContainer = document.getElementById('jobs');
  if (jobsContainer) {
    jobsContainer.addEventListener('click', () => {
      setTimeout(() => {
        const jid = currentJobId();
        document.getElementById('outreachResearchJobId').value = String(jid);
        document.getElementById('outreachStageJobId').value = String(jid);
        document.getElementById('outreachActiveJobBadge').textContent = currentJobSummary();
      }, 50);
    });
  }

  function renderCallbackCheatSheet(packet) {
    const drawer = document.createElement('details');
    drawer.style.marginTop = '6px';
    const summary = document.createElement('summary');
    summary.style.cursor = 'pointer';
    summary.style.fontWeight = '600';
    summary.textContent = 'View 30s Callback Cheat Sheet';
    drawer.append(summary);

    const card = document.createElement('div');
    card.className = 'record';
    card.style.marginTop = '6px';

    if (packet.why_this_role) {
      const why = document.createElement('p');
      why.className = 'small';
      why.innerHTML = `<strong>Why this role:</strong> `;
      const span = document.createElement('span');
      span.textContent = packet.why_this_role;
      why.append(span);
      card.append(why);
    }

    if (Array.isArray(packet.diff_summary) && packet.diff_summary.length) {
      const diffTitle = document.createElement('strong');
      diffTitle.className = 'small';
      diffTitle.textContent = 'Resume Diffs vs. Master Resume:';
      const diffList = document.createElement('ul');
      diffList.className = 'small';
      for (const d of packet.diff_summary) {
        const li = document.createElement('li');
        li.textContent = typeof d === 'string' ? d : (d.summary || JSON.stringify(d));
        diffList.append(li);
      }
      card.append(diffTitle, diffList);
    }

    if (packet.submitted_answers && typeof packet.submitted_answers === 'object') {
      const ansEntries = Object.entries(packet.submitted_answers);
      if (ansEntries.length) {
        const ansTitle = document.createElement('strong');
        ansTitle.className = 'small';
        ansTitle.textContent = 'Submitted Answers:';
        const ansList = document.createElement('ul');
        ansList.className = 'small';
        for (const [k, v] of ansEntries) {
          const li = document.createElement('li');
          li.textContent = `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`;
          ansList.append(li);
        }
        card.append(ansTitle, ansList);
      }
    }

    if (Array.isArray(packet.probe_questions) && packet.probe_questions.length) {
      const probeTitle = document.createElement('strong');
      probeTitle.className = 'small';
      probeTitle.textContent = '3 Likely Interviewer Probe Questions:';
      const probeList = document.createElement('ol');
      probeList.className = 'small';
      for (const q of packet.probe_questions) {
        const li = document.createElement('li');
        li.textContent = q;
        probeList.append(li);
      }
      card.append(probeTitle, probeList);
    }

    const rawToggle = document.createElement('details');
    const rawSummary = document.createElement('summary');
    rawSummary.className = 'small';
    rawSummary.textContent = 'Raw Snapshot JSON';
    const snapshot = document.createElement('pre');
    snapshot.textContent = JSON.stringify(packet, null, 2);
    rawToggle.append(rawSummary, snapshot);
    card.append(rawToggle);

    drawer.append(card);
    return drawer;
  }

  function render(data, summaryText) {
    status.textContent = summaryText;
    result.replaceChildren();
    for (const reply of data.replies) {
      const item = document.createElement('li');
      item.style.marginBottom = '8px';
      const classification = reply.classification.replaceAll('_', ' ');
      const headerLine = document.createElement('div');
      headerLine.textContent = [
        reply.test_only ? '[TEST ONLY]' : '',
        reply.subject || '(No subject)',
        classification,
        reply.sender,
        reply.snippet,
      ].filter(Boolean).join(' · ');
      item.append(headerLine);

      if (reply.callback_packet) {
        item.append(renderCallbackCheatSheet(reply.callback_packet));
      } else if (
        reply.id &&
        ['human_positive_reply', 'interview_invitation', 'referral_opportunity', 'request_for_info'].includes(
          reply.classification
        )
      ) {
        const link = document.createElement('button');
        link.type = 'button';
        link.className = 'secondary';
        link.style.marginTop = '4px';
        link.textContent = 'Link confirmed application';
        link.onclick = () =>
          run(async () => {
            const applications = (await api('/api/applications')).filter(
              (a) => a.status === 'confirmed' && a.confirmation
            );
            if (!applications.length) {
              render(data, 'No confirmed applications to link yet. Confirm a real application first.');
              return;
            }
            const id = window.prompt(
              applications.map((a) => `${a.id}. ${a.company} — ${a.title}`).join('\n') +
                '\nEnter the matching application ID.'
            );
            if (applications.some((a) => String(a.id) === id)) {
              const { sync_token } = await api('/api/inbox/status');
              await api('/api/inbox/link-application', {
                sync_token,
                reply_id: reply.id,
                application_id: Number(id),
              });
            }
            render(await api('/api/inbox/replies'), 'Saved Gmail replies.');
          });
        item.append(link);
      }
      result.append(item);
    }
  }

  async function run(action) {
    sync.disabled = simulate.disabled = true;
    status.textContent = 'Loading inbox results…';
    result.replaceChildren();
    try {
      await action();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      sync.disabled = simulate.disabled = false;
    }
  }

  sync.onclick = () =>
    run(async () => {
      const { sync_token } = await api('/api/inbox/status');
      const stats = await api('/api/inbox/sync', { explicit_inbox_consent: true, sync_token });
      render(
        await api('/api/inbox/replies'),
        `Gmail: ${stats.scanned} scanned, ${stats.inserted} new. Classifications are suggestions for review.`
      );
    });

  simulate.onclick = () =>
    run(async () => {
      const data = await api('/api/inbox/simulate', {});
      render(data, `${data.mode} — synthetic fixture classified without saving to database.`);
    });

  // ---------------------------------------------------------------------------
  // Wire D4 Contact Research Form
  // ---------------------------------------------------------------------------
  const researchForm = document.getElementById('outreachResearchForm');
  const cards = document.getElementById('outreachContactCards');

  function populateDeliveryFormFromDraft(contact, draftData) {
    document.getElementById('outreachStageJobId').value = String(
      draftData.job_id || document.getElementById('outreachResearchJobId').value || currentJobId()
    );
    document.getElementById('outreachStageName').value = contact.name || '';
    document.getElementById('outreachStageRole').value = contact.title || contact.role || '';
    document.getElementById('outreachStageSourceUrl').value = contact.source_url || '';
    if (contact.professional_email || draftData.recipient) {
      document.getElementById('outreachStageChannel').value = 'email';
      document.getElementById('outreachStageRecipient').value =
        contact.professional_email || draftData.recipient || '';
    }
    document.getElementById('outreachStageSubject').value = draftData.subject || '';
    document.getElementById('outreachStageBody').value = draftData.body || '';
    document.getElementById('outreachDeliveryStatus').textContent =
      'Loaded verified contact draft into B-01 Delivery Studio. Confirm recipient & stage when ready.';
  }

  researchForm.onsubmit = async (event) => {
    event.preventDefault();
    const jobIdVal = Number(document.getElementById('outreachResearchJobId').value || currentJobId());
    const sourceVal = document.getElementById('outreachResearchSourceUrl').value.trim();
    const manualName = document.getElementById('outreachManualName').value.trim();
    const manualRole = document.getElementById('outreachManualRole').value.trim();
    const manualType = document.getElementById('outreachManualType').value;
    const manualEmail = document.getElementById('outreachManualEmail').value.trim();
    const manualSnippet = document.getElementById('outreachManualSnippet').value.trim();

    cards.textContent = 'Checking public source…';
    try {
      const { sync_token } = await api('/api/inbox/status');
      const payload = {
        job_id: jobIdVal,
        source_url: sourceVal,
        employer_source_confirmed: document.getElementById('outreachResearchConfirmed').checked,
        sync_token,
      };
      if (manualName && manualRole && manualSnippet) {
        payload.manual_contact = {
          name: manualName,
          role: manualRole,
          artifact_type: manualType,
          artifact_snippet: manualSnippet,
          public_email: manualEmail,
        };
      }
      const found = await api('/api/networking/contacts/research', payload);
      cards.replaceChildren();
      if (!found.contacts.length) {
        cards.textContent = 'None verified automatically. Search for ' + found.manual_queries.join(' or ') +
          ', or expand the optional excerpt fields above to attach a verified quote from the employer page.';
      }
      for (const contact of found.contacts) {
        const card = document.createElement('article');
        card.className = 'record';
        const name = document.createElement('strong');
        name.textContent = `${contact.name} · ${contact.title}`;
        const evidence = document.createElement('p');
        evidence.className = 'small';
        evidence.textContent = `[${contact.artifact_hook.type}] ${contact.artifact_hook.snippet}`;
        const source = document.createElement('a');
        source.href = contact.source_url;
        source.target = '_blank';
        source.rel = 'noopener noreferrer';
        source.textContent = 'Public source';
        const actions = document.createElement('div');
        actions.className = 'actions';
        actions.style.marginTop = '6px';
        const draft = document.createElement('button');
        draft.type = 'button';
        draft.textContent = 'Draft 3-sentence outreach';
        const optOut = document.createElement('button');
        optOut.type = 'button';
        optOut.className = 'secondary';
        optOut.textContent = 'Mark opted out';
        const preview = document.createElement('pre');
        preview.style.marginTop = '6px';

        draft.onclick = async () => {
          try {
            const channel = document.getElementById('outreachStageChannel').value || 'email';
            const message = await api('/api/networking/contacts/draft', {
              contact_id: contact.id,
              channel,
            });
            preview.textContent = message.subject
              ? `Subject: ${message.subject}\n\n${message.body}`
              : message.body;
            populateDeliveryFormFromDraft(contact, message);
          } catch (error) {
            preview.textContent = error.message;
          }
        };
        optOut.onclick = async () => {
          try {
            const { sync_token } = await api('/api/inbox/status');
            await api(`/api/networking/contacts/${contact.id}/opt-out`, { sync_token });
            draft.disabled = optOut.disabled = true;
            preview.textContent = 'Opted out (future outreach blocked)';
          } catch (error) {
            preview.textContent = error.message;
          }
        };
        actions.append(draft, optOut);
        card.append(name, evidence, source, actions, preview);
        cards.append(card);
      }
    } catch (error) {
      cards.textContent = error.message;
    }
  };

  // ---------------------------------------------------------------------------
  // Wire B-01 Outreach Delivery & Approval Studio Buttons
  // ---------------------------------------------------------------------------
  const deliveryBadge = document.getElementById('outreachDeliveryBadge');
  const deliveryStatus = document.getElementById('outreachDeliveryStatus');
  const stageBtn = document.getElementById('outreachStageBtn');
  const approveBtn = document.getElementById('outreachApproveBtn');
  const sendBtn = document.getElementById('outreachSendBtn');
  const manualSentBtn = document.getElementById('outreachManualSentBtn');
  const importSection5Btn = document.getElementById('outreachImportSection5Btn');

  function updateDeliveryButtons() {
    approveBtn.disabled = !activeStagedDraft || !['draft', 'approved', 'failed', 'manual_required'].includes(activeStagedDraft.status);
    sendBtn.disabled = !activeStagedDraft || activeStagedDraft.status !== 'approved';
    manualSentBtn.disabled = !activeStagedDraft || activeStagedDraft.status !== 'manual_required';
    if (activeStagedDraft) {
      deliveryBadge.textContent = `Draft #${activeStagedDraft.id} · ${activeStagedDraft.status}`;
    } else {
      deliveryBadge.textContent = 'Stage -> Approve -> Send';
    }
  }

  importSection5Btn.onclick = () => {
    const rawMsg = (document.getElementById('message')?.value || '').trim();
    let subj = '';
    let body = rawMsg;
    if (rawMsg.startsWith('Subject:')) {
      const parts = rawMsg.split(/\n\n/);
      subj = parts[0].replace(/^Subject:\s*/i, '').trim();
      body = parts.slice(1).join('\n\n').trim();
    }
    document.getElementById('outreachStageJobId').value = String(currentJobId());
    document.getElementById('outreachStageName').value = document.getElementById('contactName')?.value || '';
    document.getElementById('outreachStageRole').value = document.getElementById('contactRole')?.value || '';
    document.getElementById('outreachStageSourceUrl').value = document.getElementById('contactProfile')?.value || '';
    document.getElementById('outreachStageChannel').value = document.getElementById('channel')?.value || 'email';
    document.getElementById('outreachStageSubject').value = subj;
    document.getElementById('outreachStageBody').value = body;
    deliveryStatus.textContent = 'Imported draft fields from Section 5. Verify recipient address, remove [YOUR NAME], and click Stage.';
  };

  stageBtn.onclick = async () => {
    try {
      const channel = document.getElementById('outreachStageChannel').value;
      const payload = {
        job_id: Number(document.getElementById('outreachStageJobId').value || currentJobId()),
        name: document.getElementById('outreachStageName').value.trim(),
        role: document.getElementById('outreachStageRole').value.trim(),
        recipient: document.getElementById('outreachStageRecipient').value.trim(),
        source_url: document.getElementById('outreachStageSourceUrl').value.trim(),
        channel,
        subject: channel === 'email' ? document.getElementById('outreachStageSubject').value.trim() : '',
        body: document.getElementById('outreachStageBody').value.trim(),
        user_authorized_recipient: document.getElementById('outreachStageAuthRecipient').checked,
      };
      const staged = await api('/api/networking/outreach/drafts', payload);
      activeStagedDraft = staged;
      updateDeliveryButtons();
      deliveryStatus.textContent = `Staged Outreach Draft #${staged.id} for ${staged.recipient} (${staged.job_url}). Check approval box and click "2 · Approve Staged Draft".`;
      if (typeof reload === 'function') await reload();
    } catch (error) {
      deliveryStatus.textContent = `Stage blocked: ${error.message}`;
    }
  };

  approveBtn.onclick = async () => {
    if (!activeStagedDraft) return;
    try {
      const channel = activeStagedDraft.channel;
      const provider = channel === 'linkedin' ? 'manual' : document.getElementById('outreachStageProvider').value;
      const res = await api(`/api/networking/outreach/${activeStagedDraft.id}/approve`, {
        explicit_user_approval: document.getElementById('outreachStageExplicitApproval').checked,
        review_token: activeStagedDraft.review_token,
        provider,
        reviewed_message: {
          job_url: activeStagedDraft.job_url,
          channel: activeStagedDraft.channel,
          recipient: activeStagedDraft.recipient,
          subject: activeStagedDraft.subject,
          body: activeStagedDraft.body,
        },
      });
      activeStagedDraft.status = res.status;
      activeStagedDraft.provider = res.provider;
      updateDeliveryButtons();
      deliveryStatus.textContent = `Approved Draft #${activeStagedDraft.id} via provider "${res.provider}". Click "3 · Send Approved Outreach".`;
      if (typeof reload === 'function') await reload();
    } catch (error) {
      deliveryStatus.textContent = `Approval blocked: ${error.message}`;
    }
  };

  sendBtn.onclick = async () => {
    if (!activeStagedDraft) return;
    try {
      const res = await api(`/api/networking/outreach/${activeStagedDraft.id}/send`, {
        explicit_user_approval: document.getElementById('outreachStageExplicitApproval').checked,
        review_token: activeStagedDraft.review_token,
      });
      activeStagedDraft.status = res.status;
      updateDeliveryButtons();
      if (res.status === 'sent') {
        deliveryStatus.textContent = `Sent via Gmail! Provider Message ID: ${res.provider_message_id} (${res.sent_at}).`;
      } else if (res.status === 'manual_required') {
        deliveryStatus.textContent = `${res.details || 'Manual delivery required.'} Copy the approved message, send it yourself, then click "4 · Confirm Manually Sent".`;
      } else {
        deliveryStatus.textContent = `Delivery status: ${res.status} — ${res.details || ''}`;
      }
      if (typeof reload === 'function') await reload();
    } catch (error) {
      deliveryStatus.textContent = `Send blocked: ${error.message}`;
    }
  };

  manualSentBtn.onclick = async () => {
    if (!activeStagedDraft) return;
    try {
      const res = await api(`/api/networking/outreach/${activeStagedDraft.id}/manual-sent`, {
        explicit_user_approval: document.getElementById('outreachStageExplicitApproval').checked,
        review_token: activeStagedDraft.review_token,
        confirmed_manually_sent: true,
      });
      activeStagedDraft.status = res.status;
      updateDeliveryButtons();
      deliveryStatus.textContent = `Recorded user-reported manual delivery at ${res.sent_at}.`;
      if (typeof reload === 'function') await reload();
    } catch (error) {
      deliveryStatus.textContent = `Manual confirmation blocked: ${error.message}`;
    }
  };

  run(async () => {
    const data = await api('/api/inbox/replies');
    render(
      data,
      data.replies.length
        ? 'Saved Gmail replies. Classifications are suggestions for review.'
        : 'No Gmail replies saved. Sync labeled messages or try the offline test.'
    );
  });
})();
