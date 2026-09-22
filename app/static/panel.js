// Nazorat paneli. Mantiq yo'q — faqat API'ni chaqiradi va ko'rsatadi.
'use strict';

const $ = (id) => document.getElementById(id);

// `/ofis` sahifasida panelning hamma bloki yo'q. Yo'q tugunga yozishga
// urinish butun `_yangila()` ni to'xtatib, ofisni ma'lumotsiz qoldirardi.
const qoy = (id, html) => {
  const el = $(id);
  if (el) el.innerHTML = html;
  return el;
};

const HOLAT_MATNI = {
  tugadi: 'tugadi',
  tasdiq_kutilmoqda: 'tasdiq kutilmoqda',
  aniqlik_kerak: 'aniqlik kerak',
  yakunlanmagan: 'yakunlanmagan (eski)',
  mos_agent_yoq: 'mos agent yo’q',
  ulanmagan: 'ulanmagan',
  xato: 'xato',
};

function qochir(matn) {
  const d = document.createElement('div');
  d.textContent = matn == null ? '' : String(matn);
  return d.innerHTML;
}

function holatYorlig(holat) {
  const nomi = HOLAT_MATNI[holat] || holat || '—';
  return `<span class="holat holat-${qochir(holat)}">${qochir(nomi)}</span>`;
}

function vaqtMatni(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('uz');
}

// Eng uzun zanjir ham shundan tez tugaydi; undan eskisi — tashlab ketilgan iz.
const TIRIK_MUDDAT_MS = 10 * 60 * 1000;

function yaqindami(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  return Date.now() - d.getTime() < TIRIK_MUDDAT_MS;
}

async function ol(yol, sozlama) {
  const javob = await fetch(yol, sozlama);
  if (!javob.ok) {
    let tafsilot = `${javob.status}`;
    try {
      const j = await javob.json();
      if (j.detail) tafsilot = j.detail;
    } catch (_) { /* JSON emas */ }
    throw new Error(tafsilot);
  }
  return javob.json();
}

// --- holat -------------------------------------------------------------------

let agentlar = [];
let ishlayotganRollar = new Set();  // hozir ishlayotgan agentlar (ofis uchun)
let oldingiTugatgan = null;         // zanjirda oxirgi tugatgan agent

// --- statistika --------------------------------------------------------------

async function statistikaniYangila() {
  const s = await ol('/statistika');
  const h = s.bugun_holatlar || {};
  qoy('statistika', `
    <div class="stat"><div class="son">${s.ulangan_agentlar_soni}/${s.agentlar_soni}</div>
      <div class="nom">Faol agent</div></div>
    <div class="stat ${s.tasdiq_kutilmoqda ? 'diqqat' : ''}">
      <div class="son">${s.tasdiq_kutilmoqda}</div><div class="nom">Tasdiq kutmoqda</div></div>
    <div class="stat"><div class="son">${h.tugadi || 0}</div>
      <div class="nom">Bugun bajarildi</div></div>
    <div class="stat"><div class="son">${s.bugun_sorovlar}</div>
      <div class="nom">Bugungi so'rov</div></div>`);
}

// --- agentlar ----------------------------------------------------------------

function agentBelgiRangi(agent) {
  if (!agent.amalga_oshirilgan) return 'var(--ulanmagan)';
  const holat = agent.oxirgi && agent.oxirgi.holat;
  if (holat === 'tugadi') return 'var(--tugadi)';
  if (holat === 'tasdiq_kutilmoqda') return 'var(--kutilmoqda)';
  if (holat === 'xato') return 'var(--xato)';
  if (holat === 'yakunlanmagan') return 'var(--mos-yoq)';
  return 'var(--mos-yoq)';
}

async function agentlarniYangila() {
  agentlar = await ol('/agent-faoliyati');
  window.__agentlar = agentlar;   // ofis kartochkasi shundan o'qiydi

  qoy('agentlar', agentlar.map((a, i) => `
    <div class="agent" data-agent="${i}">
      <span class="belgi" style="background:${agentBelgiRangi(a)}"></span>
      <span>
        <div class="ismi">${qochir(a.korinish)}</div>
        <div class="rol">${qochir(a.rol)}${
          a.oxirgi ? ' · ' + qochir(HOLAT_MATNI[a.oxirgi.holat] || a.oxirgi.holat) : ''
        }</div>
      </span>
      <span class="xavf xavf-${qochir(a.xavf)}">${qochir(a.xavf)}</span>
    </div>`).join(''));

  const idish = $('agentlar');
  if (idish) {
    idish.querySelectorAll('.agent').forEach((el) => {
      el.onclick = () => agentniKorsat(agentlar[Number(el.dataset.agent)]);
    });
  }

  ofisniChiz();
}

async function agentniKorsat(agent) {
  const kontrakt = await ol('/agentlar/' + encodeURIComponent(agent.rol));
  const royxat = (nomi, qatorlar) => `
    <h4>${nomi}</h4><ul>${(qatorlar || []).map((q) => `<li>${qochir(q)}</li>`).join('')}</ul>`;

  $('modal').innerHTML = `
    <button class="kichik yop" id="modal-yop">Yopish</button>
    <h3>${qochir(kontrakt.korinish)}</h3>
    <div class="rol"><code>${qochir(kontrakt.rol)}</code> &middot;
      xavf: <span class="xavf xavf-${qochir(kontrakt.xavf)}">${qochir(kontrakt.xavf)}</span> &middot;
      ${kontrakt.amalga_oshirilgan ? 'kodda ulangan' : 'kontrakt tayyor, kod yo’q'}</div>
    <p>${qochir(kontrakt.maqsad)}</p>
    ${agent.oxirgi ? `<h4>Oxirgi ishi</h4><div>${holatYorlig(agent.oxirgi.holat)}
      <span class="rol">${vaqtMatni(agent.oxirgi.vaqt)} · iz #${agent.oxirgi.iz_id}</span>
      <div class="rol">${qochir(agent.oxirgi.vazifa)}</div></div>` : ''}
    ${royxat('Qiladi (output)', kontrakt.output)}
    ${royxat('QILMAYDI (chegaralar)', kontrakt.chegaralar)}
    ${royxat('Ruxsatlar', kontrakt.ruxsatlar)}
    ${royxat('Inson tasdig’i qachon', kontrakt.tasdiq_qachon)}
    <div id="agent-tarixi"><h4>Bajargan ishlari</h4><div class="rol">yuklanmoqda…</div></div>
    ${royxat('Xato holati', kontrakt.xato_holati)}`;

  $('parda').hidden = false;
  $('modal-yop').onclick = () => { $('parda').hidden = true; };
  agentTarixiniYukla(agent.rol);
}

// Shu agent oxirgi paytda qanday vazifalarni bajargan.
async function agentTarixiniYukla(rol) {
  const idish = $('agent-tarixi');
  if (!idish) return;
  const izlar = (await ol('/izlar?chek=60')) || [];

  const ishlar = [];
  izlar.forEach((iz) => {
    (iz.qadamlar || []).forEach((q) => {
      if (q.agent === rol) {
        ishlar.push({ vaqt: iz.vaqt, iz_id: iz.id, vazifa: q.vazifa,
                      holat: q.konvert && q.konvert.holat });
      }
    });
  });

  if (!ishlar.length) {
    idish.innerHTML = '<h4>Bajargan ishlari</h4>'
      + '<div class="rol">Hali ish bajarmagan.</div>';
    return;
  }
  idish.innerHTML = '<h4>Bajargan ishlari (' + ishlar.length + ')</h4>'
    + ishlar.slice(0, 6).map((i) => `
      <div class="ish-qatori">
        ${holatYorlig(i.holat)}
        <span class="rol">${vaqtMatni(i.vaqt)} · iz #${i.iz_id}</span>
        <div>${qochir(i.vazifa || '')}</div>
      </div>`).join('');
}

$('parda').onclick = (e) => { if (e.target === $('parda')) $('parda').hidden = true; };

// 3D ofisda agent ustiga bosilganda — o'sha agentning kartochkasi ochiladi.
window.ofisAgentTanlandi = (rol) => {
  if (!rol) { $('parda').hidden = true; return; }
  const agent = (window.__agentlar || []).find((a) => a.rol === rol);
  if (agent) agentniKorsat(agent);
};

// --- ofis ko'rinishi (izometrik) ---------------------------------------------

const HOLAT_RANGI = {
  tugadi: '#7ee2a8',
  tasdiq_kutilmoqda: '#f5d97a',
  xato: '#ff9a9a',
  ulanmagan: '#8ec2ff',
  mos_agent_yoq: '#9aa4b2',
  ishlayapti: '#8ec2ff',
};
const XAVF_RANGI = { past: '#7ee2a8', orta: '#f5d97a', yuqori: '#ff9a9a' };
const BOSH = '#9aa4b2';

// Stollar joylashuvi: orqada 4 ta, oldinda 3 ta (viewBox 980x400).
const STOLLAR = [
  { x: 120, y: 130 }, { x: 340, y: 130 }, { x: 560, y: 130 }, { x: 780, y: 130 },
  { x: 120, y: 300 }, { x: 285, y: 300 }, { x: 450, y: 300 }, { x: 615, y: 300 }, { x: 780, y: 300 },
];

function agentHolati(agent) {
  if (!agent.amalga_oshirilgan) return 'ulanmagan';
  return (agent.oxirgi && agent.oxirgi.holat) || null;
}

function stolChiz(agent, joy, indeks) {
  const { x, y } = joy;
  const holat = agentHolati(agent);
  const rang = holat ? (HOLAT_RANGI[holat] || BOSH) : BOSH;
  const xavfRangi = XAVF_RANGI[agent.xavf] || BOSH;
  const holatMatni = holat ? (HOLAT_MATNI[holat] || holat) : 'bo’sh';

  // Izometrik stol: ustki romb + ikkita yon yuza.
  const usti = `${x - 75},${y} ${x},${y - 30} ${x + 75},${y} ${x},${y + 30}`;
  const chap = `${x - 75},${y} ${x},${y + 30} ${x},${y + 44} ${x - 75},${y + 14}`;
  const ong = `${x},${y + 30} ${x + 75},${y} ${x + 75},${y + 14} ${x},${y + 44}`;

  return `
  <g class="stol" data-agent="${indeks}">
    <title>${qochir(agent.korinish)} — ${qochir(holatMatni)}</title>

    <!-- xodim (stol orqasida — stol uning pastini yopadi) -->
    <ellipse cx="${x}" cy="${y - 20}" rx="28" ry="9" fill="#000" opacity=".3"/>
    <path class="xodim-tana" d="M ${x - 20} ${y - 26} q 0 -28 20 -28 q 20 0 20 28 z" fill="${rang}"/>
    <circle class="xodim-bosh" cx="${x}" cy="${y - 62}" r="11" fill="${rang}"/>

    <!-- stol -->
    <polygon class="stol-usti" points="${usti}" fill="#2a2f37"/>
    <polygon points="${chap}" fill="#1e2229"/>
    <polygon points="${ong}" fill="#171a20"/>

    <!-- ish joyi: monitor va qog'ozlar -->
    <polygon points="${x - 46},${y + 4} ${x - 18},${y - 10} ${x - 18},${y - 30} ${x - 46},${y - 16}"
             fill="#10141a" stroke="#39404b" stroke-width="1"/>
    <polygon points="${x - 44},${y + 1} ${x - 20},${y - 11} ${x - 20},${y - 27} ${x - 44},${y - 15}"
             fill="${rang}" opacity=".18"/>
    <polygon points="${x + 16},${y + 10} ${x + 34},${y + 1} ${x + 46},${y + 7} ${x + 28},${y + 16}"
             fill="#3a4049"/>
    <!-- xavf darajasi: stol oldingi qirrasi -->
    <polyline points="${x - 75},${y} ${x},${y + 30} ${x + 75},${y}"
              fill="none" stroke="${xavfRangi}" stroke-width="2.5" opacity=".85"/>

    <!-- yorliq: lavozim + ism, ostida holat -->
    <rect class="yorliq-fon" x="${x - 78}" y="${y - 119}" width="156" height="38" rx="7"/>
    <text class="yorliq-lavozim" x="${x}" y="${y - 105}" text-anchor="middle">${qochir(agent.lavozim)}</text>
    <text class="yorliq-ism" x="${x}" y="${y - 92}" text-anchor="middle">${qochir(agent.ism)}</text>
    <circle cx="${x - 62}" cy="${y - 96}" r="4" fill="${rang}"/>
    <text class="yorliq-holat" x="${x}" y="${y - 78}" text-anchor="middle"
          fill="${rang}">${qochir(holatMatni)}</text>
  </g>`;
}

function ofisniChiz() {
  const svg = $('ofis');
  if (!svg) return;

  svg.innerHTML = `
    <defs>
      <linearGradient id="pol" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#1b1e24"/>
        <stop offset="1" stop-color="#15181d"/>
      </linearGradient>
    </defs>
    <rect x="0" y="0" width="980" height="400" fill="url(#pol)" rx="10"/>
    ${agentlar.map((a, i) => (STOLLAR[i] ? stolChiz(a, STOLLAR[i], i) : '')).join('')}`;

  svg.querySelectorAll('.stol').forEach((el) => {
    el.onclick = () => agentniKorsat(agentlar[Number(el.dataset.agent)]);
  });
}

// --- zanjir ------------------------------------------------------------------

// `tugadimi = false` bo'lsa, bajarilmagan birinchi qadam "ishlayapti" bo'ladi.
function zanjirniChiz(reja, qadamlar, tugadimi) {
  if (!$('zanjir')) return;      // `/ofis` sahifasida bu blok yo'q
  if (!reja || !reja.qadamlar || !reja.qadamlar.length) {
    $('zanjir').innerHTML = `<div class="bosh">${
      reja && reja.izoh ? qochir(reja.izoh) : 'Hali so’rov yuborilmadi.'
    }</div>`;
    return;
  }

  const bajarilgan = qadamlar || [];
  // Zanjir to'xtatuvchi holatda tugagan bo'lsa, keyingi qadamlar boshlanmaydi.
  const oxirgi = bajarilgan[bajarilgan.length - 1];
  const toxtadi = oxirgi && oxirgi.konvert.holat !== 'tugadi';

  $('zanjir').innerHTML = reja.qadamlar.map((q, i) => {
    const iz = bajarilgan[i];
    const agent = agentlar.find((a) => a.rol === q.agent);
    const nomi = agent ? agent.korinish : q.agent;

    let sinf;
    let ong;
    if (iz) {
      sinf = 'bajarildi';
      ong = holatYorlig(iz.konvert.holat) +
        `<span class="rol">${Math.round(iz.davomiylik_ms / 100) / 10}s</span>`;
    } else if (!tugadimi && !toxtadi && i === bajarilgan.length) {
      sinf = 'faol';
      ong = '<span class="aylanma"></span><span class="holat holat-ishlayapti">ishlayapti</span>';
    } else {
      sinf = 'kutmoqda';
      ong = `<span class="holat holat-mos_agent_yoq">${toxtadi ? 'boshlanmadi' : 'navbatda'}</span>`;
    }

    return `<div class="qadam ${sinf}">
      <span class="tartib">${i + 1}</span>
      <span><span class="kim">${qochir(nomi)}</span>
        <div class="vazifa">${qochir(q.vazifa)}</div></span>
      <span class="ong">${ong}${q.tasdiq_kerak ? '<span class="holat holat-tasdiq_kutilmoqda">tasdiq</span>' : ''}</span>
    </div>`;
  }).join('');
}

// --- tasdiqlar ---------------------------------------------------------------

async function tasdiqlarniYangila() {
  const royxat = await ol('/tasdiq');
  if (!$('tasdiqlar')) return;   // `/ofis` sahifasida bu blok yo'q
  if (!royxat.length) {
    $('tasdiqlar').innerHTML = '<div class="bosh">Kutilayotgan tasdiq yo’q.</div>';
    return;
  }

  $('tasdiqlar').innerHTML = royxat.map((t) => `
    <div class="tasdiq-blok">
      <div class="kim">${qochir(t.korinish)}</div>
      <div class="sorov">${qochir(t.sorov)}</div>
      <div class="izohi">${qochir(t.izoh)}</div>
      <div class="tasdiq-tugma">
        <input placeholder="izoh (ixtiyoriy)" id="izoh-${t.iz_id}">
        <button class="kichik tasdiq" data-iz="${t.iz_id}" data-qaror="1">Tasdiqlash</button>
        <button class="kichik rad" data-iz="${t.iz_id}" data-qaror="0">Rad etish</button>
      </div>
      <div id="tasdiq-xato-${t.iz_id}"></div>
    </div>`).join('');

  $('tasdiqlar').querySelectorAll('button[data-iz]').forEach((el) => {
    el.onclick = () => qaror(Number(el.dataset.iz), el.dataset.qaror === '1', el);
  });
}

async function qaror(izId, tasdiqlaymi, tugma) {
  const tugmalar = $('tasdiqlar').querySelectorAll(`button[data-iz="${izId}"]`);
  tugmalar.forEach((t) => { t.disabled = true; });
  tugma.textContent = 'Yuborilmoqda…';

  try {
    const natija = await ol(`/tasdiq/${izId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tasdiqlaymi,
        izoh: ($(`izoh-${izId}`) || {}).value || '',
      }),
    });
    zanjirniChiz(natija.reja, natija.qadamlar, true);
    await hammasiniYangila();
  } catch (xato) {
    const joy = $(`tasdiq-xato-${izId}`);
    if (joy) joy.innerHTML = `<div class="xatolik">${qochir(xato.message)}</div>`;
    tugmalar.forEach((t) => { t.disabled = false; });
    tugma.textContent = tasdiqlaymi ? 'Tasdiqlash' : 'Rad etish';
  }
}

// --- tarix -------------------------------------------------------------------

async function tarixniYangila() {
  const izlar = await ol('/izlar?chek=15');

  // `yakuniy` bo'sh iz = hozir ishlayapti. Lekin faqat YAQINDAGI iz:
  // server so'rov o'rtasida to'xtasa, yakunlanmagan iz abadiy qolib ketadi
  // va zanjir "ishlayapti" bo'lib muzlab qoladi.
  const ishlayotgan = izlar.find((iz) => !iz.yakuniy && yaqindami(iz.vaqt));

  // Ofis uchun: hozir qaysi agent ishlayapti (bajarilmagan birinchi qadam)
  // va undan oldin kim tugatgan (zanjirni ko'z bilan ko'rsatish uchun).
  ishlayotganRollar = new Set();
  oldingiTugatgan = null;
  if (ishlayotgan && ishlayotgan.reja) {
    const bajarilganlar = ishlayotgan.qadamlar || [];
    const qadam = (ishlayotgan.reja.qadamlar || [])[bajarilganlar.length];
    if (qadam) ishlayotganRollar.add(qadam.agent);
    if (bajarilganlar.length) {
      oldingiTugatgan = bajarilganlar[bajarilganlar.length - 1].agent;
    }
  }

  if (ishlayotgan) {
    zanjirniChiz(ishlayotgan.reja, ishlayotgan.qadamlar, false);
  } else if (izlar.length) {
    // Hech narsa ishlamayapti — oxirgi so'rovning YAKUNIY holati ko'rsatiladi.
    // Bu shart-siz bo'lishi muhim: so'rov botdan yoki boshqa oynadan kelgan
    // bo'lsa ham, tugagach zanjir "ishlayapti" bo'lib qolib ketmasin.
    zanjirniChiz(izlar[0].reja, izlar[0].qadamlar, true);
  }

  if (!$('tarix')) return;       // `/ofis` sahifasida bu blok yo'q
  if (!izlar.length) {
    $('tarix').innerHTML = '<div class="bosh">Hali so’rov bo’lmadi.</div>';
    return;
  }

  $('tarix').innerHTML = izlar.map((iz) => {
    const zanjir = (iz.qadamlar || []).map((q) => q.korinish).join(' → ') || '—';
    const yorliq = iz.yakuniy
      ? holatYorlig(iz.yakuniy.holat)
      : '<span class="holat holat-ishlayapti">ishlayapti</span>';
    return `<div class="tarix-qator">
      <div class="tarix-bosh" data-iz="${iz.id}">
        ${yorliq}
        <span class="matn">${qochir(iz.sorov)}</span>
        <span class="vaqt">${vaqtMatni(iz.vaqt)}</span>
      </div>
      <div class="tarix-zanjir">#${iz.id} · ${qochir(zanjir)}</div>
      <div id="iz-${iz.id}"></div>
    </div>`;
  }).join('');

  $('tarix').querySelectorAll('.tarix-bosh').forEach((el) => {
    el.onclick = async () => {
      const joy = $('iz-' + el.dataset.iz);
      if (joy.innerHTML) { joy.innerHTML = ''; return; }
      const iz = await ol('/izlar/' + el.dataset.iz);
      joy.innerHTML = `<pre>${qochir(JSON.stringify(iz, null, 2))}</pre>`;
    };
  });
}

// --- so'rov yuborish ---------------------------------------------------------

$('sorov-shakl').onsubmit = async (e) => {
  e.preventDefault();
  const matn = $('sorov-matn').value.trim();
  if (!matn) return;

  $('yubor').disabled = true;
  $('yubor').textContent = 'Ishlamoqda…';
  $('sorov-xato').innerHTML = '';
  $('zanjir').innerHTML = '<div class="bosh"><span class="aylanma"></span> Router reja tuzmoqda…</div>';

  try {
    const natija = await ol('/sorov', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ matn }),
    });
    zanjirniChiz(natija.reja, natija.qadamlar, true);
    $('sorov-matn').value = '';
    await hammasiniYangila();
  } catch (xato) {
    $('sorov-xato').innerHTML = `<div class="xatolik">${qochir(xato.message)}</div>`;
    $('zanjir').innerHTML = '<div class="bosh">So’rov bajarilmadi.</div>';
  } finally {
    $('yubor').disabled = false;
    $('yubor').textContent = 'Yuborish';
  }
};

// --- jonli yangilanish (SSE) -------------------------------------------------

// Bir vaqtda bitta yangilanish. SSE va so'rov javobi bir-birini bosib
// ketmasligi uchun: ustma-ust kelgan chaqiruvlar birlashtiriladi, oxirgisi
// albatta ishlaydi. Aks holda eski javob keyin kelib, tugagan zanjirni
// yana "ishlayapti" qilib qo'yishi mumkin.
let yangilanyapti = false;
let yanaKerak = false;

async function hammasiniYangila() {
  if (yangilanyapti) {
    yanaKerak = true;
    return;
  }
  yangilanyapti = true;
  try {
    await _yangila();
    while (yanaKerak) {
      yanaKerak = false;
      await _yangila();
    }
  } finally {
    yangilanyapti = false;
  }
}

async function _yangila() {
  await Promise.all([
    statistikaniYangila(),
    agentlarniYangila(),
    tasdiqlarniYangila(),
    tarixniYangila(),
  ]).catch((xato) => console.error('yangilash xatosi', xato));

  ofisgaUzat();
}

// 3D ofis sahifasi ochiq bo'lsa — ma'lumot tayyor bo'lgach xabar beramiz.
// DIQQAT: `ofis3d.js` — ES modul, u panel.js dan KEYIN yuklanadi. Shuning
// uchun modul o'zi tayyor bo'lganda ham shu funksiyani chaqiradi, aks holda
// birinchi yangilanish yo'qolib, ofis bo'sh qolardi.
function ofisgaUzat() {
  if (typeof window.ofisYangilandi === 'function' && agentlar.length) {
    window.ofisYangilandi(agentlar, ishlayotganRollar, oldingiTugatgan);
  }
}
window.ofisgaUzat = ofisgaUzat;

function sseUlan() {
  const manba = new EventSource('/events');

  manba.onopen = () => {
    $('jonli').classList.add('ulangan');
    $('jonli-matn').textContent = 'jonli';
  };
  manba.addEventListener('yangilandi', hammasiniYangila);
  manba.onerror = () => {
    $('jonli').classList.remove('ulangan');
    $('jonli-matn').textContent = 'uzildi — qayta ulanmoqda';
    // EventSource o'zi qayta ulanadi.
  };
}

hammasiniYangila();
sseUlan();
