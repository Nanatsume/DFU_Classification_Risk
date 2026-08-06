/* Shared navbar — renders into <div id="app-nav"> present at the top of every protected page's
   <body>. Requires js/api.js (for probeMode()) and js/auth.js (for logout()) loaded first. */

function renderNav() {
  const mount = document.getElementById('app-nav');
  if (!mount) return;

  const here = location.pathname.split('/').pop() || 'index.html';
  const ALIAS = { 'crf-detail.html': 'crf-list.html' };  // detail page highlights the list tab
  const active = ALIAS[here] || here;

  const links = [
    { href: 'index.html', label: 'หน้าแรก' },
    { href: 'crf-form.html', label: 'กรอกฟอร์มใหม่' },
    { href: 'crf-list.html', label: 'ประวัติการบันทึก' },
    { href: 'capture.html', label: 'ถ่ายภาพ' },
  ];

  mount.innerHTML =
    '<div class="wrap">' +
      '<span class="brand">🦶 DFU Data Collection</span>' +
      links.map(l => '<a href="' + l.href + '"' + (active === l.href ? ' class="active"' : '') + '>' + l.label + '</a>').join('') +
      '<span class="spacer"></span>' +
      '<span class="modetag" id="nav-modetag">…</span>' +
      '<button type="button" class="logout" onclick="logout()">ออกจากระบบ</button>' +
    '</div>';

  probeMode().then(({ live, health }) => {
    const t = document.getElementById('nav-modetag');
    if (!t) return;
    if (live) {
      t.className = 'modetag live';
      t.textContent = 'LIVE' + (health && health.source === 'SimulatedSource' ? ' · กล้องจำลอง' : '');
    } else {
      t.className = 'modetag demo';
      t.textContent = 'DEMO';
    }
  });
}

document.addEventListener('DOMContentLoaded', renderNav);
