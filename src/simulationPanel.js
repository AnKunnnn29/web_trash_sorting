import { trashItems } from './mockData.js';

export function setupSimulationPanel({
  onScanItem,
  onSelectCategory,
  onResetScore,
  onResetGame
}) {
  const btnToggleSim = document.getElementById('btn-toggle-sim');
  const simPanel = document.getElementById('sim-panel');
  const rfidListEl = document.getElementById('sim-rfid-list');

  if (btnToggleSim && simPanel) {
    btnToggleSim.setAttribute('aria-expanded', 'false');
    btnToggleSim.setAttribute('aria-controls', 'sim-panel');
    btnToggleSim.addEventListener('click', () => {
      simPanel.classList.toggle('show');
      btnToggleSim.setAttribute('aria-expanded', String(simPanel.classList.contains('show')));
    });
  }

  if (rfidListEl) {
    rfidListEl.innerHTML = '';
    trashItems.forEach(item => {
      const btn = document.createElement('button');
      btn.className = 'btn-sim-item';
      btn.innerText = item.emoji;
      btn.title = `Quet ${item.name}`;
      btn.setAttribute('aria-label', `Quét thử ${item.name}`);
      btn.addEventListener('click', () => onScanItem(item));
      rfidListEl.appendChild(btn);
    });
  }

  const simGreen = document.getElementById('sim-btn-green');
  const simYellow = document.getElementById('sim-btn-yellow');
  const simRed = document.getElementById('sim-btn-red');
  const btnReset = document.getElementById('btn-sim-reset');
  const resetConfirm = document.getElementById('reset-confirm');

  if (simGreen) simGreen.addEventListener('click', () => onSelectCategory('green'));
  if (simYellow) simYellow.addEventListener('click', () => onSelectCategory('yellow'));
  if (simRed) simRed.addEventListener('click', () => onSelectCategory('red'));
  if (btnReset && resetConfirm) {
    btnReset.addEventListener('click', () => resetConfirm.showModal());
    resetConfirm.addEventListener('close', () => {
      if (resetConfirm.returnValue === 'confirm') onResetScore();
    });
  }

  window.simulateRFID = (itemId) => {
    const matched = trashItems.find(item => item.id === itemId);
    if (matched) onScanItem(matched);
  };
  window.simulateButton = (color) => onSelectCategory(color);
  window.resetGame = onResetGame;
}
