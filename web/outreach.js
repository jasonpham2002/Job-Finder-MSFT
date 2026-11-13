// Inbox Tracker mounts in the Owner B extension area.
(function () {
  const mount = document.getElementById('outreachExtensions');
  if (!mount) return;

  const heading = document.createElement('h3');
  heading.textContent = 'Inbox Tracker';
  const sync = document.createElement('button');
  sync.type = 'button';
  sync.textContent = 'Sync JobFinder-labeled Gmail';
  const simulate = document.createElement('button');
  simulate.type = 'button';
  simulate.textContent = 'Test inbox classification';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const result = document.createElement('ul');
  mount.append(heading, sync, simulate, status, result);

  async function api(path, payload) {
    const options = payload ? {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    } : {};
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Inbox request failed.');
    return data;
  }

  function render(data, summary) {
    status.textContent = summary;
    result.replaceChildren();
    for (const reply of data.replies) {
      const item = document.createElement('li');
      const classification = reply.classification.replaceAll('_', ' ');
      item.textContent = [reply.subject || '(No subject)', classification, reply.sender, reply.snippet]
        .filter(Boolean).join(' · ');
      if (reply.callback_packet) {
        const drawer = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = 'View 30s Callback Cheat Sheet';
        const snapshot = document.createElement('pre');
        snapshot.textContent = JSON.stringify(reply.callback_packet, null, 2);
        drawer.append(summary, snapshot);
        item.append(drawer);
      } else if (reply.id && ['human_positive_reply', 'interview_invitation', 'referral_opportunity',
        'request_for_info'].includes(reply.classification)) {
        const link = document.createElement('button');
        link.type = 'button';
        link.textContent = 'Link confirmed application';
        link.onclick = () => run(async () => {
          const applications = (await api('/api/applications')).filter(a => a.status === 'confirmed' && a.confirmation);
          if (!applications.length) {
            render(data, 'No confirmed applications to link.');
            return;
          }
          const id = window.prompt(applications.map(a => `${a.id}. ${a.company} — ${a.title}`).join('\n')
            + '\nEnter the matching application ID.');
          if (applications.some(a => String(a.id) === id)) {
            const {sync_token} = await api('/api/inbox/status');
            await api('/api/inbox/link-application', {sync_token, reply_id: reply.id, application_id: Number(id)});
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

  sync.onclick = () => run(async () => {
    const {sync_token} = await api('/api/inbox/status');
    const stats = await api('/api/inbox/sync', {explicit_inbox_consent: true, sync_token});
    render(await api('/api/inbox/replies'),
      `Gmail: ${stats.scanned} scanned, ${stats.inserted} new. Classifications are suggestions for review.`);
  });
  simulate.onclick = () => run(async () => {
    const data = await api('/api/inbox/simulate', {});
    render(data, data.mode);
  });

  const research = document.createElement('form');
  research.innerHTML = '<h3>Public contact research</h3><label>Job ID <input name="job" type="number" min="1" required></label> '
    + '<label>Employer team or bio URL <input name="source" type="url" required></label> '
    + '<label><input name="confirmed" type="checkbox" required> Published by this employer</label> '
    + '<button>Find contacts</button>';
  const cards = document.createElement('div');
  mount.prepend(research, cards);
  research.onsubmit = async (event) => {
    event.preventDefault();
    const fields = new FormData(research);
    cards.textContent = 'Checking public source…';
    try {
      const {sync_token} = await api('/api/inbox/status');
      const found = await api('/api/networking/contacts/research', {
        job_id: Number(fields.get('job')), source_url: fields.get('source'), employer_source_confirmed: true, sync_token,
      });
      cards.replaceChildren();
      if (!found.contacts.length) cards.textContent = 'None verified. Search for ' + found.manual_queries.join(' or ');
      for (const contact of found.contacts) {
        const card = document.createElement('article');
        const name = document.createElement('strong');
        name.textContent = `${contact.name} · ${contact.title}`;
        const evidence = document.createElement('p');
        evidence.textContent = contact.artifact_hook.snippet;
        const source = document.createElement('a');
        source.href = contact.source_url;
        source.textContent = 'Public source';
        const draft = document.createElement('button');
        draft.textContent = 'Draft outreach';
        const optOut = document.createElement('button');
        optOut.textContent = 'Mark opted out';
        const preview = document.createElement('pre');
        draft.onclick = async () => {
          try {
            const message = await api('/api/networking/contacts/draft', {contact_id: contact.id});
            preview.textContent = `${message.subject}\n\n${message.body}`;
          } catch (error) {
            preview.textContent = error.message;
          }
        };
        optOut.onclick = async () => {
          try {
            const {sync_token} = await api('/api/inbox/status');
            await api(`/api/networking/contacts/${contact.id}/opt-out`, {sync_token});
            draft.disabled = optOut.disabled = true;
            preview.textContent = 'Opted out';
          } catch (error) {
            preview.textContent = error.message;
          }
        };
        card.append(name, evidence, source, draft, optOut, preview);
        cards.append(card);
      }
    } catch (error) {
      cards.textContent = error.message;
    }
  };
  run(async () => {
    const data = await api('/api/inbox/replies');
    render(data, data.replies.length ? 'Saved Gmail replies. Classifications are suggestions for review.'
      : 'No Gmail replies saved. Sync labeled messages or try the offline test.');
  });
})();
