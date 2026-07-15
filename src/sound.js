let audioCtx = null;

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

export const sound = {
  init: () => {
    try {
      initAudio();
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
  }
};
