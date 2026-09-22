// Ofis harakatini brauzersiz sinash.
//
// `ofis-model.js` — sof mantiq (three.js ga bog'liq emas), shuning uchun uni
// Node'da to'g'ridan-to'g'ri yurgizib, minglab kadrni bir necha soniyada
// tekshirsa bo'ladi. Brauzerda buni qilib bo'lmaydi: oyna ko'rinmasa
// `requestAnimationFrame` to'xtaydi va o'lchov yolg'on chiqadi.
//
// Ishga tushirish:  node tests/ofis_simulyatsiya.mjs

import {
  BOLIMLAR, ISH_STOLLARI, MAJLIS_JOYLARI, OSHXONA_JOYLARI, OfisAgenti,
  majlisOrindigi, majlisdami, majlisniBoshla, majlisniTugat,
} from '../app/static/ofis-model.js';

// TASODIF BOSHQARILADI. Model `Math.random()` ishlatadi (agent qayerga
// yurishini tanlaydi). Boshqarilmasa test goh o'tadi, goh yiqiladi va
// yiqilganini QAYTA CHIQARIB bo'lmaydi. Shuning uchun urug'ni argumentdan
// olamiz: `node ofis_simulyatsiya.mjs --seed=7`.
const URUG = Number((process.argv.find((a) => a.startsWith('--seed=')) || '--seed=1').slice(7));
let _holat = URUG >>> 0 || 1;
Math.random = () => {
  // xorshift32 — oddiy, tez va takrorlanadigan.
  _holat ^= _holat << 13; _holat >>>= 0;
  _holat ^= _holat >>> 17;
  _holat ^= _holat << 5;  _holat >>>= 0;
  return _holat / 4294967296;
};

const KADR = 1 / 60;          // 60 fps
const KADRLAR = 60 * 60;      // 60 soniya
const ISHLAYOTGANLAR = new Set([
  'marketing', 'legal-review', 'hr-assist', 'proposal-builder',
  'data-query', 'smm-analyst',
]);

// Model `performance.now()` ga tayanadi (kutish oralig'i uchun). Simulyatsiya
// real vaqtdan tez ketadi, shuning uchun soatni o'zimiz surib boramiz.
let soat = 0;
globalThis.performance = { now: () => soat };

const bolimIchida = (bolimId, x, y) => {
  const b = BOLIMLAR.find((v) => v.id === bolimId);
  return b && x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h;
};
const qaysiBolim = (x, y) => {
  const b = BOLIMLAR.find((v) => x >= v.x && x < v.x + v.w && y >= v.y && y < v.y + v.h);
  return b ? b.id : 'yolak';
};

const agentlar = Object.keys(ISH_STOLLARI).map((rol) => new OfisAgenti({
  rol, korinish: rol, amalga_oshirilgan: true, xavf: 'past', ism: rol,
}));

// Kimdir ishlayapti, qolgani bo'sh.
agentlar.forEach((a) => {
  if (ISHLAYOTGANLAR.has(a.rol)) a.holatniQoy('ishlayapti', [10, 33]);
});

const borgan = new Map(agentlar.map((a) => [a.rol, new Set()]));
let engYaqin = Infinity;
let engYaqinKim = null;
let boshBegonaXonada = 0;
const begonaJoylar = new Map();
let stolidaIshladi = 0;      // ishlayotgan agent o'z kompyuteri oldida
let tushlikQildi = 0;        // oshxona stulida o'tirgan
const oshxonaJoyi = new Set(OSHXONA_JOYLARI.map(([x, y]) => `${x},${y}`));

for (let kadr = 0; kadr < KADRLAR; kadr++) {
  soat += KADR * 1000;
  agentlar.forEach((a) => a.yangila(KADR));

  // Uzluksiz (interpolyatsiyalangan) joylashuvlar orasidagi eng kichik masofa.
  const joylar = agentlar.map((a) => a.joylashuv());
  for (let i = 0; i < joylar.length; i++) {
    for (let j = i + 1; j < joylar.length; j++) {
      const d = Math.hypot(joylar[i].px - joylar[j].px, joylar[i].py - joylar[j].py);
      if (d < engYaqin) {
        engYaqin = d;
        engYaqinKim = [agentlar[i].rol, agentlar[j].rol];
      }
    }
  }

  agentlar.forEach((a) => {
    borgan.get(a.rol).add(qaysiBolim(a.x, a.y));
    const stol = ISH_STOLLARI[a.rol];
    if (a.holat === 'ishlayapti' && a.otirgan
        && a.x === stol.otirish[0] && a.y === stol.otirish[1]) {
      stolidaIshladi++;
    }
    if (a.otirgan && oshxonaJoyi.has(`${a.x},${a.y}`)) tushlikQildi++;
    // Bo'sh agent BOSHQA BO'LIMDA turib qolmasligi kerak. Yo'lak, oshxona
    // va majlis xonasi — umumiy joylar, ular "begona" emas. Yo'lda
    // ketayotgan agent ham o'tkinchi, hisobga olinmaydi.
    const joy = qaysiBolim(a.x, a.y);
    const umumiy = joy === 'yolak' || joy === 'oshxona' || joy === 'majlis';
    if (!a.holat && !a.tushlikda && !a.yol.length
        && !umumiy && joy !== ISH_STOLLARI[a.rol].bolim) {
      boshBegonaXonada++;
      const k = `${a.rol} -> ${joy}`;
      begonaJoylar.set(k, (begonaJoylar.get(k) || 0) + 1);
    }
  });
}

// KATAK — bitta katakning piksel o'lchami; masofani katakda ifodalaymiz.
const { KATAK } = await import('../app/static/ofis-model.js');
const yaqinKatak = engYaqin / KATAK;

const xatolar = [];

// 1. Hech qachon ustma-ust tushmasin. Gavda diametri ~0.55 katak.
if (yaqinKatak < 0.6) {
  xatolar.push(`ustma-ust: ${engYaqinKim} orasi ${yaqinKatak.toFixed(2)} katak`);
}

// 2. Bo'sh agent o'z xonasidan chiqmasin.
if (boshBegonaXonada > 0) {
  xatolar.push(`bo'sh agent begona xonada: ${boshBegonaXonada} kadr`);
}

// 3a. Ishlayotgan agent kompyuteri oldida ham o'tirsin.
if (stolidaIshladi === 0) xatolar.push('hech kim stolida ishlamadi');

// 3b. Kimdir tushlikka chiqib, oshxona stulida o'tirsin.
if (tushlikQildi === 0) xatolar.push('hech kim oshxonada ovqatlanmadi');

// 3. Ishlayotganlarning ko'pchiligi boshqa bo'limlarga chiqsin.
//    Har biri emas: agent vaqtining yarmida o'z stolida ishlaydi,
//    shuning uchun bittasi 60 soniya davomida chiqmasligi ham normal.
const chiqqanlar = [...ISHLAYOTGANLAR].filter((rol) => {
  const oz = ISH_STOLLARI[rol].bolim;
  return [...borgan.get(rol)].some((b) => b !== oz && b !== 'yolak');
});
if (chiqqanlar.length < ISHLAYOTGANLAR.size - 2) {
  xatolar.push(`faqat ${chiqqanlar.length} agent boshqa bo'limga chiqdi`);
}

// --- 2-qism: savol chiqdi -> hamma majlisga yig'iladi -> tarqaladi ----------

const MAJLIS_XONASI = BOLIMLAR.find((b) => b.id === 'majlis');
const majlisdaMi = (a) => a.x >= MAJLIS_XONASI.x && a.x < MAJLIS_XONASI.x + MAJLIS_XONASI.w
  && a.y >= MAJLIS_XONASI.y && a.y < MAJLIS_XONASI.y + MAJLIS_XONASI.h;

if (MAJLIS_JOYLARI.length < agentlar.length) {
  xatolar.push(
    `majlis o'rindig'i yetmaydi: ${MAJLIS_JOYLARI.length} ta stul, `
    + `${agentlar.length} ta agent`,
  );
}

// Har agentga o'zgarmas o'rindiq biriktiramiz (ofis3d.js shunday qiladi).
agentlar.forEach((a, i) => { a.majlisJoyi = majlisOrindigi(i); });
majlisniBoshla('aniqlik_kerak');

let yigilganKadr = 0;
for (let kadr = 0; kadr < 60 * 60; kadr++) {   // 60 soniya — yetib borishga
  soat += KADR * 1000;
  agentlar.forEach((a) => a.yangila(KADR));
  if (agentlar.every(majlisdaMi)) { yigilganKadr = kadr; break; }
}
// Xonaga kirish bilan o'rindiqqa cho'kish bir xil emas: oxirgi kataklar
// tor, kimdir yo'lni to'sib qolsa agent aylanib o'tadi. Hamma o'tirguncha
// (yoki 20 soniya) kutamiz.
const orindiqda = new Set(MAJLIS_JOYLARI.map(([x, y]) => `${x},${y}`));
const otirganSoni = () => agentlar.filter(
  (a) => a.otirgan && orindiqda.has(`${a.x},${a.y}`),
).length;
let otirishSoniya = 0;
for (let kadr = 0; kadr < 60 * 20; kadr++) {
  soat += KADR * 1000;
  agentlar.forEach((a) => a.yangila(KADR));
  otirishSoniya = (kadr + 1) * KADR;
  if (otirganSoni() === agentlar.length) break;
}
const hammaYigildi = agentlar.every(majlisdaMi);
const otirganlar = otirganSoni();
if (hammaYigildi && otirganlar !== agentlar.length) {
  xatolar.push(`majlisda ${agentlar.length - otirganlar} kishi tik turibdi`);
}
if (!hammaYigildi) {
  const qolgan = agentlar.filter((a) => !majlisdaMi(a)).map((a) => a.rol);
  xatolar.push(`majlisga yig'ilmadi: ${qolgan.join(', ')}`);
}

// O'rindiqlar takrorlanmasin — ikki kishi bitta stulda o'tirmasin.
const orindiqlar = new Set(agentlar.map((a) => `${a.x},${a.y}`));
if (orindiqlar.size !== agentlar.length) {
  xatolar.push(`majlisda ${agentlar.length - orindiqlar.size} ta joy takrorlandi`);
}

// Savol yopildi — tarqalishadi.
majlisniTugat();
let tarqaldi = false;
for (let kadr = 0; kadr < 60 * 40; kadr++) {
  soat += KADR * 1000;
  agentlar.forEach((a) => a.yangila(KADR));
  if (!majlisdami() && agentlar.some((a) => !majlisdaMi(a))) { tarqaldi = true; break; }
}
if (!tarqaldi) xatolar.push('majlisdan keyin tarqalishmadi');

console.log(JSON.stringify({
  kadrlar: KADRLAR,
  eng_yaqin_katak: +yaqinKatak.toFixed(3),
  eng_yaqin_kim: engYaqinKim,
  bosh_begona_xonada_kadr: boshBegonaXonada,
  begona_joylar: Object.fromEntries(begonaJoylar),
  stolida_ishladi_kadr: stolidaIshladi,
  oshxonada_ovqatlandi_kadr: tushlikQildi,
  borgan: Object.fromEntries([...borgan].map(([r, v]) => [r, [...v]])),
  agentlar_soni: agentlar.length,
  majlis: {
    hamma_yigildi: hammaYigildi,
    yigilish_soniya: +(yigilganKadr * KADR).toFixed(1),
    turli_orindiq: orindiqlar.size,
    orindiqda_otirdi: otirganlar,
    otirish_soniya: +otirishSoniya.toFixed(1),
    tarqaldi,
  },
  xatolar,
}, null, 2));

process.exit(xatolar.length ? 1 : 0);
