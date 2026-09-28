import { describe, expect, it } from 'vitest';
import { parseBluetoothKeyboardPayload, parseHardwareMessage } from '../src/hardwareConnection.js';

describe('hardware message parsing', () => {
  it('accepts RFID and physical bin-button messages', () => {
    expect(parseHardwareMessage('{"type":"rfid","itemId":"banana"}')).toEqual({
      type: 'rfid',
      itemId: 'banana'
    });
    expect(parseHardwareMessage('{"type":"button","color":"yellow"}')).toEqual({
      type: 'button',
      color: 'yellow'
    });
  });

  it('ignores ESP32 boot logs, malformed JSON and unsupported colors', () => {
    expect(parseHardwareMessage('rst:0x1 (POWERON_RESET)')).toBeNull();
    expect(parseHardwareMessage('{bad json')).toBeNull();
    expect(parseHardwareMessage('{"type":"button","color":"blue"}')).toBeNull();
  });

  it('accepts only the dedicated EcoSort Bluetooth keyboard payload', () => {
    expect(parseBluetoothKeyboardPayload('ECOSORT:plastic_bag')).toEqual({
      type: 'rfid',
      itemId: 'plastic_bag'
    });
    expect(parseBluetoothKeyboardPayload('hello')).toBeNull();
    expect(parseBluetoothKeyboardPayload('ECOSORT:bad item')).toBeNull();
  });
});
