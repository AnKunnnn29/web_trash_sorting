let audioCtx = null;
let encouragementIndex = 0;

const ENCOURAGEMENTS = [
  'Không sao đâu, mình thử lại nhé!',
  'Suýt đúng rồi! Bé hãy suy nghĩ thêm một chút nhé!',
  'Đừng bỏ cuộc, bé làm được mà!'
];

function initAudio() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
}

function playNote(freq, type, duration, startTime, volume = 0.1) {
  initAudio();
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  
  osc.type = type;
  osc.frequency.setValueAtTime(freq, startTime);
  
  // ADSR / Amplitude envelope
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(volume, startTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
  
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  
  osc.start(startTime);
  osc.stop(startTime + duration);
}

function playClap(startTime, volume = 0.18) {
  const duration = 0.11;
  const frameCount = Math.ceil(audioCtx.sampleRate * duration);
  const buffer = audioCtx.createBuffer(1, frameCount, audioCtx.sampleRate);
  const channel = buffer.getChannelData(0);
  for (let index = 0; index < frameCount; index++) {
    const envelope = Math.pow(1 - index / frameCount, 3.2);
    channel[index] = (Math.random() * 2 - 1) * envelope;
  }

  const source = audioCtx.createBufferSource();
  const bandpass = audioCtx.createBiquadFilter();
  const highpass = audioCtx.createBiquadFilter();
  const gain = audioCtx.createGain();
  source.buffer = buffer;
  bandpass.type = 'bandpass';
  bandpass.frequency.value = 1450;
  bandpass.Q.value = 0.65;
  highpass.type = 'highpass';
  highpass.frequency.value = 650;
  gain.gain.setValueAtTime(volume, startTime);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
  source.connect(bandpass);
  bandpass.connect(highpass);
  highpass.connect(gain);
  gain.connect(audioCtx.destination);
  source.start(startTime);
  source.stop(startTime + duration);
}

function speak(text, { rate = 0.94, pitch = 1.06, volume = 1 } = {}) {
  if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) return;
  const utterance = new SpeechSynthesisUtterance(String(text));
  utterance.lang = 'vi-VN';
  utterance.rate = rate;
  utterance.pitch = pitch;
  utterance.volume = volume;
  const vietnameseVoice = window.speechSynthesis.getVoices()
    .find(voice => voice.lang?.toLowerCase().startsWith('vi'));
  if (vietnameseVoice) utterance.voice = vietnameseVoice;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

export const sound = {
  init: () => {
    try {
      initAudio();
      window.speechSynthesis?.getVoices();
    } catch (e) {
      console.warn("AudioContext init failed", e);
    }
  },
  
  playCorrect: () => {
    try {
      initAudio();
      const now = audioCtx.currentTime;
      // Uplifting C major arpeggio chime (C4 -> E4 -> G4 -> C5)
      playNote(261.63, 'sine', 0.4, now, 0.15); 
      playNote(329.63, 'sine', 0.4, now + 0.08, 0.15); 
      playNote(392.00, 'sine', 0.4, now + 0.16, 0.15); 
      playNote(523.25, 'sine', 0.6, now + 0.24, 0.2); 
      [0, 0.11, 0.23, 0.38, 0.56, 0.71].forEach((offset, index) => {
        playClap(now + offset, 0.15 + (index % 3) * 0.025);
      });
    } catch (e) {
      console.warn("Failed playing correct sound", e);
    }
  },
  
  playIncorrect: () => {
    try {
      initAudio();
      const now = audioCtx.currentTime;
      // Soft falling sliding warning tone
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(196.00, now); 
      osc.frequency.exponentialRampToValueAtTime(155.56, now + 0.45); 
      
      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.45);
      
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      
      osc.start(now);
      osc.stop(now + 0.45);
      speak(ENCOURAGEMENTS[encouragementIndex % ENCOURAGEMENTS.length]);
      encouragementIndex += 1;
    } catch (e) {
      console.warn("Failed playing incorrect sound", e);
    }
  },
  
  playScan: () => {
    try {
      initAudio();
      const now = audioCtx.currentTime;
      // Quick scanner blip
      playNote(880.00, 'triangle', 0.12, now, 0.08);
    } catch (e) {
      console.warn("Failed playing scan sound", e);
    }
  },
  
  playWelcome: () => {
    try {
      initAudio();
      const now = audioCtx.currentTime;
      // Gentle welcoming chord
      playNote(392.00, 'sine', 0.5, now, 0.08);
      playNote(523.25, 'sine', 0.5, now + 0.1, 0.08);
      playNote(659.25, 'sine', 0.8, now + 0.2, 0.12);
    } catch (e) {
      console.warn("Failed playing welcome sound", e);
    }
  },

  announceRfidItem: (itemName, categoryName) => {
    try {
      const friendlyName = String(itemName).replaceAll('/', ' hoặc ');
      speak(`${friendlyName}. Thuộc nhóm rác ${categoryName}.`, {
        rate: 0.9,
        pitch: 1.02
      });
    } catch (e) {
      console.warn('Failed announcing RFID item', e);
    }
  }
};
