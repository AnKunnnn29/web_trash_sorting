export function setupWorldEffects() {
  const mascots = [...document.querySelectorAll('.decorative-mascot')];

  if (!mascots.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  if (!('IntersectionObserver' in window)) {
    mascots.forEach((mascot) => mascot.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      entry.target.classList.toggle('is-visible', entry.isIntersecting);
    });
  }, { threshold: 0.15 });

  mascots.forEach((mascot) => observer.observe(mascot));
}
