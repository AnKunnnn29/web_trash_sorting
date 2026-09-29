import { sortableTrashItems } from './mockData.js';

let callbacks = {};
let bluetoothKeyboardBound = false;
let bluetoothKeyboardBuffer = '';
let lastBluetoothKeyAt = 0;

const BLUETOOTH_KEYBOARD_PREFIX = 'ECOSORT:';
const BLUETOOTH_KEY_TIMEOUT_MS = 1200;

export function parseBluetoothKeyboardPayload(data) {
  const value = String(data).trim();
  if (!value.toUpperCase().startsWith(BLUETOOTH_KEYBOARD_PREFIX)) return null;

  const itemId = value.slice(BLUETOOTH_KEYBOARD_PREFIX.length);
  if (!/^[a-z0-9_]+$/.test(itemId)) return null;
  return { type: 'rfid', itemId };
}

function isEditableTarget(target) {
  return target instanceof HTMLElement && (
    target.isContentEditable ||
    ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)
  );
}

function dispatchRfidItem(itemId) {
  const matched = sortableTrashItems.find(item => item.id === itemId);
  if (matched) callbacks.onScanItem?.(matched);
}

function setupBluetoothKeyboardConnection() {
  if (bluetoothKeyboardBound) return;
  bluetoothKeyboardBound = true;

  document.addEventListener('keydown', event => {
    if (isEditableTarget(event.target) || event.ctrlKey || event.altKey || event.metaKey) return;

    const now = Date.now();
    if (now - lastBluetoothKeyAt > BLUETOOTH_KEY_TIMEOUT_MS) bluetoothKeyboardBuffer = '';
    lastBluetoothKeyAt = now;

    if (event.key === 'Enter') {
      const message = parseBluetoothKeyboardPayload(bluetoothKeyboardBuffer);
      bluetoothKeyboardBuffer = '';
      if (!message) return;

      event.preventDefault();
      event.stopPropagation();
      dispatchRfidItem(message.itemId);
      return;
    }

    if (event.key.length !== 1) return;
    bluetoothKeyboardBuffer = `${bluetoothKeyboardBuffer}${event.key}`.slice(-80);
  }, true);
}

export function setupHardwareConnection(options) {
  callbacks = options;
  setupBluetoothKeyboardConnection();
}
