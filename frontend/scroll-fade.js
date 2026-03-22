// Fade-in on scroll for main sections
function revealOnScroll() {
  const sections = document.querySelectorAll('.hero-section, .storytelling-section, .lead-magnet-section, .authority-block, .cta-final-block, .metodo-borgia-section, .case-story-block, .section-fade');
  const reveal = (entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  };
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(reveal);
  }, { threshold: 0.18 });
  sections.forEach(section => {
    section.classList.add('section-fade');
    observer.observe(section);
  });
}
document.addEventListener('DOMContentLoaded', revealOnScroll);
