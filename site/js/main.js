(function(){
  const nav = document.querySelector('nav');
  const toggle = document.querySelector('.mobile-toggle');
  const links = document.querySelector('.nav-links');

  if (toggle && links) {
    toggle.addEventListener('click', () => {
      links.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!nav.contains(e.target)) {
        links.classList.remove('open');
      }
    });
  }

  const current = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(a => {
    const href = a.getAttribute('href');
    if (href && current.includes(href) && href !== '/') {
      a.classList.add('active');
    }
    if (href === '/' && (current === '/' || current === '' || current.endsWith('index.html'))) {
      a.classList.add('active');
    }
  });

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  document.querySelectorAll('pre code').forEach(block => {
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.style.cssText = 'position:absolute;top:8px;right:8px;padding:4px 10px;font-size:11px;border-radius:6px;border:1px solid var(--border);background:var(--bg-card);color:var(--text-muted);cursor:pointer;opacity:0;transition:opacity .2s;';
    const pre = block.parentElement;
    pre.style.position = 'relative';
    pre.appendChild(btn);
    pre.addEventListener('mouseenter', () => btn.style.opacity = '1');
    pre.addEventListener('mouseleave', () => btn.style.opacity = '0');
    btn.addEventListener('click', () => {
      navigator.clipboard.writeText(block.textContent).then(() => {
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 1500);
      });
    });
  });
})();