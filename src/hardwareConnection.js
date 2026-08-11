import { sortableTrashItems } from './mockData.js';

let socket = null;
let reconnectInterval = null;

export function setupHardwareConnection({ onScanItem, onSelectCategory }) {
  const statusDot = document.getElementById('esp-status-dot');
  const statusText = document.getElementById('esp-status-text');
  const ip = localStorage.getItem('esp32_ip');

  const setHardwareStatus = (state, text) => {
    if (statusDot) statusDot.className = `status-dot${state ? ` ${state}` : ''}`;
    if (statusText) statusText.innerText = text;
  };

  if (socket) {
    socket.close();
  }

  if (reconnectInterval) {
    clearInterval(reconnectInterval);
    reconnectInterval = null;
  }

  if (!ip) {
    setHardwareStatus('', 'Chưa thiết lập IP');
    return;
  }

  setHardwareStatus('status-dot-connecting', 'Đang kết nối...');

  try {
    socket = new WebSocket(`ws://${ip}:81`);

    const connectTimeout = setTimeout(() => {
      if (socket && socket.readyState !== WebSocket.OPEN) {
        console.log('[WebSocket] Connection timeout, skipping auto-reconnect');
        socket.close();
        setHardwareStatus('', 'Chưa kết nối — sẽ thử lại sau');
      }
    }, 3000);

    socket.onopen = () => {
      clearTimeout(connectTimeout);
      console.log(`WebSocket connected to ESP32: ${ip}`);
      setHardwareStatus('active status-dot-success', 'Đã kết nối trạm');
    };

    socket.onmessage = (event) => {
      handleHardwareMessage(event.data, { onScanItem, onSelectCategory });
    };

    socket.onclose = () => {
      clearTimeout(connectTimeout);
      console.log('[WebSocket] Connection closed');
      setHardwareStatus('', 'Chưa kết nối');
    };

    socket.onerror = () => {
      clearTimeout(connectTimeout);
      console.log('[WebSocket] Connection failed (ESP32 not ready)');
    };
  } catch (err) {
    console.log('[WebSocket] Init failed:', err.message);
  }
}

function handleHardwareMessage(data, { onScanItem, onSelectCategory }) {
  try {
    const msg = JSON.parse(data);
    console.log('Nhận tín hiệu phần cứng:', msg);

    if (msg.type === 'rfid') {
      const matched = sortableTrashItems.find(item => item.id === msg.itemId);
      if (matched) onScanItem(matched);
    } else if (msg.type === 'button') {
      onSelectCategory(msg.color);
    }
  } catch (e) {
    console.warn('Tín hiệu phần cứng không hợp lệ:', data);
  }
}
