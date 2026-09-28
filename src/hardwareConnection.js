import { sortableTrashItems } from './mockData.js';

let socket = null;
let serialPort = null;
let serialReader = null;
let serialReadTask = null;
let callbacks = {};
let serialButtonBound = false;
let bluetoothKeyboardBound = false;
let bluetoothKeyboardBuffer = '';
let lastBluetoothKeyAt = 0;

const BLUETOOTH_KEYBOARD_PREFIX = 'ECOSORT:';
const BLUETOOTH_KEY_TIMEOUT_MS = 1200;

function getHardwareElements() {
  return {
    statusDot: document.getElementById('esp-status-dot'),
    statusText: document.getElementById('esp-status-text'),
    connectButton: document.getElementById('btn-connect-rfid'),
    errorText: document.getElementById('rfid-connection-error')
  };
}

function setHardwareStatus(state, text) {
  const { statusDot, statusText } = getHardwareElements();
  if (statusDot) statusDot.className = `status-dot${state ? ` ${state}` : ''}`;
  if (statusText) statusText.innerText = text;
}

function setHardwareError(message = '') {
  const { errorText } = getHardwareElements();
  if (errorText) errorText.textContent = message;
}

export function parseHardwareMessage(data) {
  try {
    const message = JSON.parse(String(data).trim());
    if (message.type === 'rfid' && typeof message.itemId === 'string') {
      return { type: 'rfid', itemId: message.itemId };
    }
    if (message.type === 'button' && ['green', 'yellow', 'red'].includes(message.color)) {
      return { type: 'button', color: message.color };
    }
  } catch {
    return null;
  }
  return null;
}

export function parseBluetoothKeyboardPayload(data) {
  const value = String(data).trim();
  if (!value.toUpperCase().startsWith(BLUETOOTH_KEYBOARD_PREFIX)) return null;
  const itemId = value.slice(BLUETOOTH_KEYBOARD_PREFIX.length);
  if (!/^[a-z0-9_]+$/.test(itemId)) return null;
  return { type: 'rfid', itemId };
}

function handleHardwareMessage(data) {
  const message = parseHardwareMessage(data);
  if (!message) return;

  console.log('Nhận tín hiệu phần cứng:', message);
  if (message.type === 'rfid') {
    const matched = sortableTrashItems.find(item => item.id === message.itemId);
    if (matched) callbacks.onScanItem?.(matched);
  } else if (message.type === 'button') {
    callbacks.onSelectCategory?.(message.color);
  }
}

async function disconnectSerial() {
  const { connectButton } = getHardwareElements();
  const port = serialPort;
  const readTask = serialReadTask;
  serialPort = null;

  try {
    await serialReader?.cancel();
  } catch {
    // The reader may already be closed after a physical disconnect.
  }
  if (readTask) await readTask;

  try {
    await port?.close();
  } catch {
    // The OS may have already released the port.
  }
  serialReadTask = null;

  if (connectButton) {
    connectButton.textContent = 'Kết nối RFID USB';
    connectButton.setAttribute('aria-pressed', 'false');
  }
  setHardwareStatus('', 'Chờ thẻ RFID Bluetooth');
}

async function readSerialMessages(port) {
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (port.readable && serialPort === port) {
      serialReader = port.readable.getReader();
      try {
        while (true) {
          const { value, done } = await serialReader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split(/\r?\n/);
          buffer = lines.pop() || '';
          lines.forEach(handleHardwareMessage);
        }
      } finally {
        serialReader.releaseLock();
        serialReader = null;
      }
    }
  } catch (error) {
    if (serialPort === port) setHardwareError(`Mất kết nối RFID: ${error.message}`);
  }
}

async function toggleSerialConnection() {
  const { connectButton } = getHardwareElements();
  setHardwareError('');

  if (serialPort) {
    await disconnectSerial();
    return;
  }

  try {
    setHardwareStatus('status-dot-connecting', 'Đang chờ chọn cổng USB...');
    serialPort = await navigator.serial.requestPort();
    await serialPort.open({ baudRate: 115200 });
    if (connectButton) {
      connectButton.textContent = 'Ngắt RFID USB';
      connectButton.setAttribute('aria-pressed', 'true');
    }
    setHardwareStatus('active status-dot-success', 'Đã kết nối RFID USB');
    const connectedPort = serialPort;
    serialReadTask = readSerialMessages(connectedPort).finally(async () => {
      if (serialPort !== connectedPort) return;
      try {
        await connectedPort.close();
      } catch {
        // The operating system may already have closed a removed device.
      }
      serialPort = null;
      serialReadTask = null;
      if (connectButton) {
        connectButton.textContent = 'Kết nối RFID USB';
        connectButton.setAttribute('aria-pressed', 'false');
      }
      setHardwareStatus('', 'Chưa kết nối');
    });
  } catch (error) {
    serialPort = null;
    setHardwareStatus('', 'Chờ thẻ RFID Bluetooth');
    if (error.name !== 'NotFoundError') {
      setHardwareError(`Không kết nối được RFID: ${error.message}`);
    }
  }
}

function setupSerialConnection() {
  const { connectButton } = getHardwareElements();
  if (!connectButton || serialButtonBound) return;
  serialButtonBound = true;

  if (!('serial' in navigator)) {
    connectButton.hidden = true;
    return;
  }

  connectButton.addEventListener('click', toggleSerialConnection);
  navigator.serial.addEventListener?.('disconnect', event => {
    if (event.target === serialPort) void disconnectSerial();
  });
}

function isEditableTarget(target) {
  return target instanceof HTMLElement && (
    target.isContentEditable ||
    ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)
  );
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
      setHardwareError('');
      setHardwareStatus('active status-dot-success', 'Đã nhận thẻ RFID Bluetooth');
      handleHardwareMessage(JSON.stringify(message));
      return;
    }

    if (event.key.length !== 1) return;
    bluetoothKeyboardBuffer = `${bluetoothKeyboardBuffer}${event.key}`.slice(-80);
  }, true);
}

function setupWebSocketConnection() {
  const ip = localStorage.getItem('esp32_ip');
  if (socket) socket.close();
  if (!ip || serialPort) return;

  setHardwareStatus('status-dot-connecting', 'Đang kết nối Wi-Fi...');
  try {
    socket = new WebSocket(`ws://${ip}:81`);
    const connectTimeout = setTimeout(() => {
      if (socket?.readyState !== WebSocket.OPEN) socket?.close();
    }, 3000);

    socket.onopen = () => {
      clearTimeout(connectTimeout);
      setHardwareStatus('active status-dot-success', 'Đã kết nối trạm Wi-Fi');
    };
    socket.onmessage = event => handleHardwareMessage(event.data);
    socket.onclose = () => {
      clearTimeout(connectTimeout);
      if (!serialPort) setHardwareStatus('', 'Chưa kết nối');
    };
    socket.onerror = () => clearTimeout(connectTimeout);
  } catch (error) {
    setHardwareError(`Không kết nối được ESP32 qua Wi-Fi: ${error.message}`);
  }
}

export function setupHardwareConnection(options) {
  callbacks = options;
  setupBluetoothKeyboardConnection();
  setupSerialConnection();
  setupWebSocketConnection();
}
