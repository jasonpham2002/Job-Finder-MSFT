// Owner A frontend extension module (Job Discovery, D1 Pre-Flight, D2 Anti-Slop/ATS Preview, D3 Co-Pilot, D5 Gaps).
// Mounts into #pipelineExtensions without modifying web/app.js.
(function () {
  const mount = document.getElementById('pipelineExtensions');
  if (!mount) return;
  mount.innerHTML = '<p class="small"><strong>Pipeline Extensions (Owner A):</strong> Pre-Flight Shield (D1), Anti-Slop + ATS Preview (D2), Co-Pilot Packet (D3), and Gap-to-Proof (D5) mount here as tasks A-01..A-05 are completed.</p>';
})();
