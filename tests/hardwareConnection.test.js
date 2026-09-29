import { describe, expect, it } from 'vitest';
import { parseBluetoothKeyboardPayload } from '../src/hardwareConnection.js';

describe('Bluetooth RFID payload parsing', () => {
  it('accepts only the dedicated EcoSort Bluetooth keyboard payload', () => {
    expect(parseBluetoothKeyboardPayload('ECOSORT:plastic_bag')).toEqual({
      type: 'rfid',
      itemId: 'plastic_bag'
    });
    expect(parseBluetoothKeyboardPayload('hello')).toBeNull();
    expect(parseBluetoothKeyboardPayload('ECOSORT:bad item')).toBeNull();
    expect(parseBluetoothKeyboardPayload('ECOSORT:')).toBeNull();
  });
});
