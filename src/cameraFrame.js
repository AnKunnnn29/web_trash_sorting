let offscreenCanvas = null;

export function getCroppedCanvas(video) {
  if (!offscreenCanvas) {
    offscreenCanvas = document.createElement('canvas');
    offscreenCanvas.width = 300;
    offscreenCanvas.height = 300;
  }

  const ctx = offscreenCanvas.getContext('2d', { willReadFrequently: true });
  const vw = video.videoWidth;
  const vh = video.videoHeight;

  const cw = vw * 0.6;
  const ch = vh * 0.6;
  const cx = (vw - cw) / 2;
  const cy = (vh - ch) / 2;

  ctx.drawImage(video, cx, cy, cw, ch, 0, 0, offscreenCanvas.width, offscreenCanvas.height);
  return offscreenCanvas;
}

export function captureWebcamFrame(video = document.getElementById('webcam')) {
  if (!video || video.readyState !== 4) return null;

  const canvas = getCroppedCanvas(video);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
  return dataUrl.split(',')[1];
}
