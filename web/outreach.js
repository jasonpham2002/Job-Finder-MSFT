// Owner B frontend extension module (D4 Artifact Contacts, Gmail/Outlook Send, Inbox Classifier & D2 Callback Trigger).
// Mounts into #outreachExtensions without modifying web/app.js.
(function () {
  const mount = document.getElementById('outreachExtensions');
  if (!mount) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Test inbox classification';
  const result = document.createElement('pre');
  result.setAttribute('aria-live', 'polite');
  mount.append(button, result);

  button.onclick = async () => {
    button.disabled = true;
    try {
      const response = await fetch('/api/inbox/simulate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: '{}',
      });
      if (!response.ok) throw new Error('Inbox simulation failed.');
      const data = await response.json();
      result.textContent = [data.mode, ...data.replies.map(
        reply => reply.subject + ' — ' + reply.classification
      )].join('\n');
    } catch (error) {
      result.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
})();
