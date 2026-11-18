// ═══════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════
// Menu acessível: item vira botão de teclado; no celular/ícones o nome aparece em "title".
document.querySelectorAll('.nav-item').forEach(n => {
  n.setAttribute('role', 'button'); n.tabIndex = 0;
  n.title = n.textContent.trim();
  n.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); n.click(); } });
});
document.querySelector('.nav-item.active')?.setAttribute('aria-current', 'page');
document.getElementById('toast-area').setAttribute('aria-live', 'polite');
document.getElementById('modal-overlay').setAttribute('role', 'dialog');
document.getElementById('modal-overlay').setAttribute('aria-modal', 'true');
document.addEventListener('keydown', e => {            // Esc fecha a janela aberta
  if (e.key === 'Escape' && document.getElementById('modal-overlay').style.display !== 'none') closeModal();
});

(async () => {
  document.getElementById('content').innerHTML =
    '<div class="skel-grid"><div class="skel"></div><div class="skel"></div><div class="skel"></div><div class="skel"></div><div class="skel alto"></div></div>';
  await loadData();
  render();
})();
