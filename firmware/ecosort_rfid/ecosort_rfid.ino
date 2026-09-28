#include <SPI.h>
#include <MFRC522.h>
#include <BleKeyboard.h>

#define RFID_SS_PIN 5
#define RFID_RST_PIN 22

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
BleKeyboard bleKeyboard("EcoSort RFID", "EcoSort", 100);

struct TagMapping {
  byte uid[4];
  const char* itemId;
};

// 24 loai rac + 6 the lap lai cho cac vat pho bien.
const TagMapping TAGS[] = {
  {{0x09, 0x9B, 0x11, 0x07}, "banana"},
  {{0x87, 0x1C, 0x48, 0x95}, "apple"},
  {{0xA7, 0x8D, 0x11, 0x95}, "orange"},
  {{0xF7, 0x84, 0x0A, 0x95}, "egg_shell"},
  {{0x57, 0x46, 0xA6, 0x95}, "bread"},
  {{0xA7, 0x03, 0x30, 0x95}, "leaf"},
  {{0xB7, 0xA9, 0x1E, 0x95}, "bone"},
  {{0x77, 0xF1, 0x46, 0x95}, "coffee"},
  {{0x07, 0xBE, 0x0C, 0x96}, "bottle"},
  {{0x87, 0x40, 0x7F, 0x95}, "soda_can"},
  {{0xF7, 0x7B, 0xB6, 0x95}, "newspaper"},
  {{0x47, 0xA4, 0xBF, 0x95}, "cardboard"},
  {{0x57, 0x79, 0xBF, 0x95}, "book"},
  {{0x67, 0xBC, 0xE2, 0x95}, "shampoo_bottle"},
  {{0x57, 0xD0, 0x24, 0x95}, "glass_bottle"},
  {{0x47, 0x66, 0xD7, 0x95}, "metal_fork"},
  {{0xE7, 0x57, 0xBB, 0x95}, "milk_carton"},
  {{0x97, 0x8D, 0xE4, 0x95}, "plastic_bag"},
  {{0xE7, 0xB7, 0xE4, 0x95}, "battery"},
  {{0xD7, 0xCD, 0xAD, 0x95}, "lightbulb"},
  {{0x97, 0x81, 0xB9, 0x95}, "thermometer"},
  {{0x87, 0x9E, 0x28, 0x95}, "chemical_bottle"},
  {{0xD7, 0x5A, 0x5A, 0x95}, "electronic"},
  {{0x67, 0x47, 0x15, 0x95}, "aerosol"},

  {{0x07, 0x8A, 0x17, 0x96}, "banana"},
  {{0xD7, 0xA8, 0x5B, 0x95}, "bottle"},
  {{0x77, 0x33, 0xF8, 0x95}, "soda_can"},
  {{0x47, 0x45, 0xC9, 0x95}, "newspaper"},
  {{0xF7, 0x53, 0xDF, 0x95}, "milk_carton"},
  {{0x47, 0xC5, 0xC3, 0x95}, "plastic_bag"}
};

const size_t TAG_COUNT = sizeof(TAGS) / sizeof(TAGS[0]);

const char* findItemId(const MFRC522::Uid& scanned) {
  if (scanned.size != 4) return nullptr;
  for (size_t tagIndex = 0; tagIndex < TAG_COUNT; tagIndex++) {
    bool matches = true;
    for (byte uidIndex = 0; uidIndex < 4; uidIndex++) {
      if (scanned.uidByte[uidIndex] != TAGS[tagIndex].uid[uidIndex]) {
        matches = false;
        break;
      }
    }
    if (matches) return TAGS[tagIndex].itemId;
  }
  return nullptr;
}

void printUnknownUid(const MFRC522::Uid& scanned) {
  Serial.print("{\"type\":\"rfid_unknown\",\"uid\":\"");
  for (byte index = 0; index < scanned.size; index++) {
    if (index > 0) Serial.print(" ");
    if (scanned.uidByte[index] < 0x10) Serial.print("0");
    Serial.print(scanned.uidByte[index], HEX);
  }
  Serial.println("\"}");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  SPI.begin(18, 19, 23, RFID_SS_PIN);
  rfid.PCD_Init();
  delay(100);
  rfid.PCD_AntennaOn();
  bleKeyboard.begin();
  Serial.println("{\"type\":\"ready\",\"device\":\"ecosort-rfid\"}");
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(30);
    return;
  }

  const char* itemId = findItemId(rfid.uid);
  if (itemId) {
    Serial.print("{\"type\":\"rfid\",\"itemId\":\"");
    Serial.print(itemId);
    Serial.println("\"}");

    if (bleKeyboard.isConnected()) {
      bleKeyboard.print("ECOSORT:");
      bleKeyboard.print(itemId);
      bleKeyboard.write(KEY_RETURN);
    }
  } else {
    printUnknownUid(rfid.uid);
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(500);
}
