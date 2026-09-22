// Ofis MODELI — xarita, bo'limlar, yo'l topish va agent holati.
//
// Bu fayl CHIZMAYDI: u faqat "ofis qanday tuzilgan va agent qayerda" degan
// bilimni saqlaydi. 2D va 3D ko'rinishlar shu bitta modeldan foydalanadi —
// shuning uchun ikkalasida ham agentlar bir xil yuradi.
// Ofis xaritasi — grid asosida, kodda belgilangan (tashqi muharrir kerak emas).
//
// Agentlar SOHASI bo'yicha bo'limlarga ajratilgan: bir ish ustida ishlaydigan
// agentlar bir xonada o'tiradi. Shunda ofisga qaraganda kim nima qilishi
// darrov ko'rinadi.

const KATAK = 16;              // bitta katak piksel o'lchami (dunyo birligida)
const XARITA_ENI = 50;
const XARITA_BOYI = 38;

// Katak turlari
const POL = 0;      // yurish mumkin (pol)
const DEVOR = 1;
const STOL = 2;      // ish stoli — yurib bo'lmaydi
const OSIMLIK = 3;
const MAJLIS = 4;    // majlis stoli
const OSHXONA = 5;   // oshxona javoni
const GILAM = 6;     // pol, lekin boshqa rangda (yo'lak)
const SHKAF = 7;
const OSH_STOL = 8;  // oshxonadagi ovqatlanish stoli
const BEZAK = 9;     // divan, jurnal stolchasi, javon, muzlatgich

const YURIB_BOLADI = new Set([POL, GILAM]);

// Bo'limlar. `rang` — 3D da pol tusi, ro'yxatda yorliq rangi.
// BO'LIM RANGLARI — 2026-09-09 da qayta tanlandi.
//
// Oldin hammasi bir xil bej tusda edi (#e8d8b8, #e6d3c4, #dcd9c0…) —
// farqi ko'zga ilinmasdi va ofis yassi, monoxrom ko'rinardi. Endi
// har bo'lim o'z RANG OILASIGA ega, lekin qiymati (yorug'ligi) bir xil
// darajada — shunda ajralib turadi, lekin ola-bula bo'lib ketmaydi.
//
// Rang MA'NOGA bog'langan: savdo iliq (mijoz), texnik salqin (hisob),
// yurist jiddiy (binafsha), oshxona to'q sariq (ovqat).
const BOLIMLAR = [
  { id: 'savdo',     nom: 'Savdo bo‘limi',      x: 1,  y: 1,  w: 21, h: 12, rang: '#f2cf93' },
  { id: 'marketing', nom: 'Marketing bo‘limi',  x: 26, y: 1,  w: 23, h: 12, rang: '#f0b3b0' },
  { id: 'texnik',    nom: 'Texnik bo‘lim',      x: 1,  y: 17, w: 21, h: 10, rang: '#a9d4cf' },
  { id: 'hr',        nom: 'HR xonasi',          x: 26, y: 17, w: 11, h: 10, rang: '#c8dd9c' },
  { id: 'yurist',    nom: 'Yurist kabineti',    x: 38, y: 17, w: 11, h: 10, rang: '#c8bee4' },
  { id: 'majlis',    nom: 'Majlis xonasi',      x: 1,  y: 31, w: 20, h: 6,  rang: '#a9c8e8' },
  { id: 'oshxona',   nom: 'Oshxona',            x: 26, y: 31, w: 23, h: 6,  rang: '#f5c08c' },
];

// Yo'laklar (gilam bilan belgilanadi)
const YOLAKLAR = [
  { x: 23, y: 1,  w: 2,  h: 36 },   // vertikal — hamma bo'limni bog'laydi
  { x: 1,  y: 14, w: 48, h: 2 },    // yuqori qavat <-> pastki qavat
  { x: 1,  y: 28, w: 48, h: 2 },    // majlis va oshxona oldida
];

// Eshiklar: devorda ochiladigan kataklar
const ESHIKLAR = [
  [22, 6], [22, 7],        // Savdo -> vertikal yo'lak
  [25, 6], [25, 7],        // Marketing -> vertikal yo'lak
  [22, 21], [22, 22],      // Texnik -> vertikal yo'lak
  [25, 21], [25, 22],      // HR -> vertikal yo'lak
  [10, 13], [11, 13],      // Savdo -> gorizontal yo'lak
  [35, 13], [36, 13],      // Marketing -> gorizontal yo'lak
  [10, 16], [11, 16],      // Texnik -> gorizontal yo'lak
  [30, 16], [31, 16],      // HR -> gorizontal yo'lak
  [42, 16], [43, 16],      // Yurist -> gorizontal yo'lak
  [4, 30], [5, 30],        // Majlis -> pastki yo'lak (chap)
  [10, 30], [11, 30],      // Majlis -> pastki yo'lak (o'rta)
  [16, 30], [17, 30],      // Majlis -> pastki yo'lak (o'ng)
  [35, 30], [36, 30],      // Oshxona -> pastki yo'lak
];

// Agent stollari. `bolim` — qaysi xonada o'tiradi (ro'yxat va 3D yorliq uchun).
const ISH_STOLLARI = {
  // Savdo bo'limi
  'proposal-builder': { stol: [4, 4],   otirish: [4, 5],   bolim: 'savdo' },
  'sales-strategy':   { stol: [10, 4],  otirish: [10, 5],  bolim: 'savdo' },
  'tender-watch':     { stol: [16, 4],  otirish: [16, 5],  bolim: 'savdo' },
  'kp-tracker':       { stol: [4, 9],   otirish: [4, 10],  bolim: 'savdo' },
  // Marketing bo'limi
  'marketing':        { stol: [30, 4],  otirish: [30, 5],  bolim: 'marketing' },
  'competitor-watch': { stol: [36, 4],  otirish: [36, 5],  bolim: 'marketing' },
  'smm-analyst':      { stol: [42, 4],  otirish: [42, 5],  bolim: 'marketing' },
  // Texnik bo'lim
  'product-spec':     { stol: [4, 20],  otirish: [4, 21],  bolim: 'texnik' },
  'catalog-admin':    { stol: [10, 20], otirish: [10, 21], bolim: 'texnik' },
  'price-monitor':    { stol: [16, 20], otirish: [16, 21], bolim: 'texnik' },
  'data-query':       { stol: [10, 24], otirish: [10, 25], bolim: 'texnik' },
  'hvac-calc':        { stol: [16, 24], otirish: [16, 25], bolim: 'texnik' },
  // Alohida kabinetlar
  'hr-assist':        { stol: [30, 20], otirish: [30, 21], bolim: 'hr' },
  'legal-review':     { stol: [42, 20], otirish: [42, 21], bolim: 'yurist' },
};

// Majlis stoli atrofidagi o'rindiqlar. Stol x:4..16, y:33..34 —
// yuqorisida va pastida bittadan qator. O'rindiq AGENTDAN KO'P bo'lishi
// kerak: yetmasa `majlisOrindigi` aylanib, ikki kishi bitta stulga
// tushadi.
const MAJLIS_JOYLARI = [
  [4, 32], [6, 32], [8, 32], [10, 32], [12, 32], [14, 32], [16, 32],
  [4, 35], [6, 35], [8, 35], [10, 35], [12, 35], [14, 35], [16, 35],
];

// Oshxonadagi ovqatlanish stollari va ular atrofidagi o'rindiqlar.
// Har stolda 4 kishilik joy — tushlikka chiqqan xodim shu yerda o'tiradi.
const OSH_STOLLARI = [[30, 34], [36, 34], [42, 34]];
const OSHXONA_JOYLARI = OSH_STOLLARI.flatMap(([x, y]) => [
  [x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1],
]);

// Bo'sh vaqtda sayr qilinadigan joylar (yo'laklar bo'ylab).
const SAYR_JOYLARI = [
  [23, 8], [23, 20], [23, 33], [12, 14], [33, 14], [44, 14],
  [12, 28], [33, 28], [44, 28],
];

const OSIMLIK_JOYLARI = [
  [2, 12], [21, 2], [21, 12], [27, 12], [48, 2], [48, 12],
  [2, 26], [21, 26], [48, 26], [2, 36], [21, 36], [48, 36],
];

// --- xona bezaklari ---------------------------------------------------------
//
// Xonalar bo'm-bo'sh edi: to'rt devor, bir nechta stol va katta bo'sh pol.
// Shuning uchun ofis sovuq va tugallanmagan ko'rinardi. Quyidagilar shu
// bo'shliqni to'ldiradi.
//
// POLDAGI bezak KATAKNI EGALLAYDI (`BEZAK`) — agent uning ustidan yurmaydi,
// aylanib o'tadi. Shuning uchun joylashuv ehtiyotkorlik bilan tanlangan:
// eshikdan ish stoligacha bo'lgan yo'l HECH QAYERDA to'silmaydi.
//
//   `buril` — radianda. 0 = suyanchiq shimolda (-z), ya'ni divan janubga
//   (+z) qaraydi. π = teskarisi.
const BEZAKLAR = [
  // Savdo — mijoz kutish burchagi
  { tur: 'divan',      x: 13, y: 9,  en: 3, boy: 1, buril: 0 },
  { tur: 'stolcha',    x: 14, y: 11, en: 1, boy: 1 },
  // Marketing — dam olish burchagi
  { tur: 'divan',      x: 30, y: 9,  en: 3, boy: 1, buril: 0 },
  { tur: 'stolcha',    x: 31, y: 11, en: 1, boy: 1 },
  // Texnik — hujjat javoni chap devor bo'ylab
  { tur: 'javon',      x: 1,  y: 23, en: 1, boy: 2, buril: Math.PI / 2 },
  // HR — suhbat burchagi (divan janubiy devorga suyangan)
  { tur: 'divan',      x: 27, y: 25, en: 3, boy: 1, buril: Math.PI },
  { tur: 'stolcha',    x: 28, y: 23, en: 1, boy: 1 },
  // Yurist — mijoz divani va kitob javoni
  { tur: 'divan',      x: 39, y: 24, en: 2, boy: 1, buril: 0 },
  { tur: 'javon',      x: 38, y: 18, en: 1, boy: 2, buril: Math.PI / 2 },
  // Oshxona — muzlatgich javon yonida
  { tur: 'muzlatgich', x: 27, y: 32, en: 1, boy: 1, buril: 0 },
];

// DEVORGA osilganlar pol katagini egallamaydi — ular devor yuzasida turadi.
//
//   `x, y` — DEVOR katagi;
//   `yon`  — qaysi tomonga qaraydi (xona ichiga): [dx, dy].
const DEVOR_BEZAKLARI = [
  // Majlis xonasi — stol boshidagi doska
  { tur: 'doska', x: 0,  y: 33, yon: [1, 0], en: 2 },
  // Texnik bo'lim — hisob-kitob doskasi
  { tur: 'doska', x: 4,  y: 16, yon: [0, 1], en: 2 },
  // Marketing — kampaniya doskasi
  { tur: 'doska', x: 30, y: 0,  yon: [0, 1], en: 2 },

  // Ramkalar: har xonada ikkitadan, turli rangda.
  { tur: 'ramka', x: 6,  y: 0,  yon: [0, 1], tus: '#3f7f9e' },
  { tur: 'ramka', x: 8,  y: 0,  yon: [0, 1], tus: '#c47a3d' },
  { tur: 'ramka', x: 22, y: 3,  yon: [-1, 0], tus: '#6d8f4e' },
  { tur: 'ramka', x: 49, y: 6,  yon: [-1, 0], tus: '#a2557d' },
  { tur: 'ramka', x: 34, y: 0,  yon: [0, 1], tus: '#4f6fa8' },
  { tur: 'ramka', x: 0,  y: 19, yon: [1, 0], tus: '#c47a3d' },
  { tur: 'ramka', x: 0,  y: 22, yon: [1, 0], tus: '#3f7f9e' },
  { tur: 'ramka', x: 25, y: 19, yon: [1, 0], tus: '#6d8f4e' },
  { tur: 'ramka', x: 49, y: 20, yon: [-1, 0], tus: '#a2557d' },
  { tur: 'ramka', x: 39, y: 16, yon: [0, 1], tus: '#4f6fa8' },
  { tur: 'ramka', x: 40, y: 30, yon: [0, 1], tus: '#c47a3d' },
  { tur: 'ramka', x: 44, y: 30, yon: [0, 1], tus: '#6d8f4e' },
];

function xaritaYasa() {
  const t = [];
  for (let y = 0; y < XARITA_BOYI; y++) t.push(new Array(XARITA_ENI).fill(DEVOR));

  const toldir = (r, qiymat) => {
    for (let y = r.y; y < r.y + r.h; y++) {
      for (let x = r.x; x < r.x + r.w; x++) {
        if (y >= 0 && y < XARITA_BOYI && x >= 0 && x < XARITA_ENI) t[y][x] = qiymat;
      }
    }
  };

  BOLIMLAR.forEach((b) => toldir(b, POL));
  YOLAKLAR.forEach((y) => toldir(y, GILAM));
  ESHIKLAR.forEach(([x, y]) => { t[y][x] = GILAM; });

  // Jihoz
  Object.values(ISH_STOLLARI).forEach(({ stol }) => { t[stol[1]][stol[0]] = STOL; });
  OSIMLIK_JOYLARI.forEach(([x, y]) => { if (t[y][x] === POL) t[y][x] = OSIMLIK; });

  // Majlis stoli
  for (let y = 33; y <= 34; y++) for (let x = 4; x <= 16; x++) t[y][x] = MAJLIS;
  // Oshxona javoni
  for (let x = 28; x <= 36; x++) t[32][x] = OSHXONA;
  // Ovqatlanish stollari
  OSH_STOLLARI.forEach(([x, y]) => { t[y][x] = OSH_STOL; });
  // Shkaflar
  for (let y = 18; y <= 22; y++) t[y][35] = SHKAF;
  for (let x = 44; x <= 47; x++) t[25][x] = SHKAF;

  // Bezaklar — FAQAT bo'sh polga. Shart qo'yilgani bejiz emas: bezak
  // xato joylashtirilsa ish stolini yoki yo'lakni yeb qo'ymasin va
  // agent o'z stoliga bora olmay qolmasin.
  BEZAKLAR.forEach(({ x, y, en, boy }) => {
    for (let j = 0; j < boy; j++) {
      for (let i = 0; i < en; i++) {
        if (t[y + j]?.[x + i] === POL) t[y + j][x + i] = BEZAK;
      }
    }
  });

  return t;
}

const XARITA = xaritaYasa();

// Katak qaysi bo'limga tegishli (3D pol rangi va yorliq uchun).
function bolimTop(x, y) {
  return BOLIMLAR.find(
    (b) => x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h,
  ) || null;
}

function yuribBoladi(x, y) {
  if (x < 0 || y < 0 || x >= XARITA_ENI || y >= XARITA_BOYI) return false;
  return YURIB_BOLADI.has(XARITA[y][x]);
}

// --- bandlik: agentlar bir-birining ustidan o'tmasin ------------------------
//
// Har agent turgan katagini "band" deb belgilaydi. Yo'l topishda band
// kataklar chetlab o'tiladi — shuning uchun ikki agent bir katakda uchrashib
// qolmaydi, biri ikkinchisini aylanib o'tadi.
const BAND = new Map();   // "x,y" -> rol

// Endigina bo'shagan kataklar: kalit -> { rol, vaqt }. Bitta qadam ~310 ms,
// shuning uchun yarim qadamcha "iliq" turadi — orqadagi agent yetib olib
// oldindagining ustiga minib ketmaydi.
const BOSHAGAN = new Map();
const SOVUSH_MS = 220;

// Agent egallagan kataklar. Qadam davomida IKKITA katak band bo'ladi —
// turgani va kirayotgani. Aks holda hamkasbi yarim yo'lda ichiga kirib
// qolardi.
function bandBelgila(rol, ...kataklar) {
  const yangi = new Set(kataklar.map(([x, y]) => `${x},${y}`));
  BAND.forEach((egasi, kalit) => {
    if (egasi !== rol) return;
    BAND.delete(kalit);
    if (!yangi.has(kalit)) BOSHAGAN.set(kalit, { rol, vaqt: performance.now() });
  });
  yangi.forEach((kalit) => BAND.set(kalit, rol));
}

function bandmi(x, y, ozi) {
  const kalit = `${x},${y}`;
  const egasi = BAND.get(kalit);
  if (egasi !== undefined) return egasi !== ozi;

  const iz = BOSHAGAN.get(kalit);
  if (!iz) return false;
  if (performance.now() - iz.vaqt > SOVUSH_MS) {
    BOSHAGAN.delete(kalit);
    return false;
  }
  return iz.rol !== ozi;
}

// Bo'lim ichidagi tasodifiy bo'sh katak.
function bolimJoyi(bolimId) {
  const b = BOLIMLAR.find((x) => x.id === bolimId);
  if (!b) return null;
  for (let urinish = 0; urinish < 40; urinish++) {
    const x = b.x + Math.floor(Math.random() * b.w);
    const y = b.y + Math.floor(Math.random() * b.h);
    if (yuribBoladi(x, y) && !bandmi(x, y, null)) return [x, y];
  }
  return null;
}

// Oshxonada bo'sh o'rindiq (band bo'lmagani).
function tushlikJoyi() {
  const bosh = OSHXONA_JOYLARI.filter(
    ([x, y]) => yuribBoladi(x, y) && !bandmi(x, y, null),
  );
  if (!bosh.length) return null;
  return bosh[Math.floor(Math.random() * bosh.length)];
}

function ozXonaJoyi(rol) {
  const stol = ISH_STOLLARI[rol];
  return stol ? bolimJoyi(stol.bolim) : null;
}

function begonaXonaJoyi(rol) {
  const stol = ISH_STOLLARI[rol];
  const boshqalar = BOLIMLAR.filter(
    (b) => b.id !== (stol && stol.bolim) && b.id !== 'oshxona',
  );
  if (!boshqalar.length) return null;
  const b = boshqalar[Math.floor(Math.random() * boshqalar.length)];
  return bolimJoyi(b.id);
}

// --- yo'l topish (BFS — grid kichik, yetarli) --------------------------------

function yolTop(boshlanish, tugash, ozi = null) {
  const kalit = (x, y) => `${x},${y}`;
  if (!yuribBoladi(tugash[0], tugash[1])) return [];
  if (boshlanish[0] === tugash[0] && boshlanish[1] === tugash[1]) return [];

  const navbat = [boshlanish];
  const kelgan = new Map([[kalit(...boshlanish), null]]);

  while (navbat.length) {
    const [x, y] = navbat.shift();
    if (x === tugash[0] && y === tugash[1]) break;
    for (const [dx, dy] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) {
      const nx = x + dx;
      const ny = y + dy;
      const k = kalit(nx, ny);
      if (kelgan.has(k) || !yuribBoladi(nx, ny)) continue;
      // Band katak — aylanib o'tiladi. Nishonning o'zi ham istisno emas:
      // ikki agent bitta katakda turib qolmasligi kerak.
      if (bandmi(nx, ny, ozi)) continue;
      kelgan.set(k, [x, y]);
      navbat.push([nx, ny]);
    }
  }

  if (!kelgan.has(kalit(...tugash))) return [];

  const yol = [];
  let joriy = tugash;
  while (joriy) {
    yol.unshift(joriy);
    joriy = kelgan.get(kalit(...joriy));
  }
  return yol.slice(1); // birinchi katak — hozirgi joy
}


// --- holat ranglari (ko'rinishlar uchun umumiy) ------------------------------

export const HOLAT_RANGI_OFIS = {
  tugadi: '#4f9d69',
  tasdiq_kutilmoqda: '#d9a441',
  aniqlik_kerak: '#8b6bb1',
  xato: '#c9553d',
  ishlayapti: '#3d7ea6',
  bosh: '#8a8175',
};

export const XAVF_RANGI_OFIS = { past: '#4f9d69', orta: '#d9a441', yuqori: '#c9553d' };

// Agentlarning kiyim ranglari (bir-biridan ajralib tursin).
export const KIYIM = {
  'price-monitor': '#4f8ef7',
  'competitor-watch': '#e0793a',
  'product-spec': '#3aa88a',
  'data-query': '#8b6fd6',
  'marketing': '#d94f8a',
  'sales-strategy': '#c86a2f',
  'proposal-builder': '#2f8f8f',
  'hr-assist': '#d6b83a',
  'legal-review': '#5c6bc0',
  'catalog-admin': '#7a9e3f',
  'tender-watch': '#c94f6d',
  'smm-analyst': '#b8558f',
  'kp-tracker': '#5aa0c4',
  'hvac-calc': '#6b8f5e',
};

// Agent jinsi — 3D figuraning gavdasi, sochi va kiyimi shunga qarab
// yasaladi. Ismlardan olingan (kontraktlardagi `ism` maydoni).
export const JINS = {
  'price-monitor': 'ayol',        // Zara
  'competitor-watch': 'erkak',    // Karim
  'product-spec': 'erkak',        // Sardor
  'data-query': 'erkak',          // Doston
  'marketing': 'ayol',            // Malika
  'sales-strategy': 'erkak',      // Bekzod
  'proposal-builder': 'erkak',    // Temur
  'hr-assist': 'ayol',            // Hilola
  'legal-review': 'erkak',        // Laziz
  'catalog-admin': 'ayol',        // Nodira
  'tender-watch': 'erkak',        // Jasur
  'smm-analyst': 'ayol',          // Nilufar
  'kp-tracker': 'ayol',           // Aziza
  'hvac-calc': 'erkak',           // Rustam
};

// Soch ranglari — hamma bir xil bo'lib qolmasin.
export const SOCH = {
  'price-monitor': 0x2b1d16,
  'competitor-watch': 0x3a2a1c,
  'product-spec': 0x241a13,
  'data-query': 0x1f1712,
  'marketing': 0x4a2418,
  'sales-strategy': 0x33261d,
  'proposal-builder': 0x2a1f18,
  'hr-assist': 0x53321f,
  'legal-review': 0x231a14,
  'catalog-admin': 0x30201a,
  'tender-watch': 0x2d2119,
  'smm-analyst': 0x1c1512,
  'kp-tracker': 0x3b2a1e,
  'hvac-calc': 0x272019,
};

export const HOLAT_MATNI = {
  tugadi: 'tugadi',
  tasdiq_kutilmoqda: 'tasdiq kutmoqda',
  aniqlik_kerak: 'savol bor',
  xato: 'xato',
  mos_agent_yoq: "bo‘sh",
  ulanmagan: "ulanmagan",
};

export const YURISH_TEZLIGI = 3.2; // katak/sekund

// --- umumiy majlis ----------------------------------------------------------
//
// Savol chiqqanda (`aniqlik_kerak`) yoki tasdiq kutilganda butun jamoa
// majlis xonasiga yig'iladi — kim javob berishini birga hal qilishadi.
// Savol yopilgach tarqalishadi. Bu bitta agentning emas, BUTUN ofisning
// holati, shuning uchun modul darajasida turadi.
const YIGILISH = {
  faol: false,
  sabab: null,        // 'aniqlik_kerak' | 'tasdiq_kutilmoqda'
  tarqash: 0,         // 0 dan katta bo'lsa — shu vaqtdan keyin tarqalishadi
};

// Savol yopilgandan keyin yana shuncha o'tirib turishadi (ms).
const MAJLIS_QOLDIQ_MS = 4000;

function majlisniBoshla(sabab) {
  YIGILISH.faol = true;
  YIGILISH.sabab = sabab;
  YIGILISH.tarqash = 0;
}

function majlisniTugat() {
  if (!YIGILISH.faol || YIGILISH.tarqash) return;
  // Darrov emas — bir necha soniya o'tirib, keyin tarqalishadi.
  YIGILISH.tarqash = performance.now() + MAJLIS_QOLDIQ_MS;
}

function majlisdami() {
  if (!YIGILISH.faol) return false;
  if (YIGILISH.tarqash && performance.now() > YIGILISH.tarqash) {
    YIGILISH.faol = false;
    YIGILISH.sabab = null;
    YIGILISH.tarqash = 0;
    return false;
  }
  return true;
}

// Har agentga o'zgarmas o'rindiq — har yangilanishda joyi sakramasin.
function majlisOrindigi(indeks) {
  return MAJLIS_JOYLARI[indeks % MAJLIS_JOYLARI.length];
}

class OfisAgenti {
  constructor(malumot) {
    this.rol = malumot.rol;
    this.malumot = malumot;
    const stol = ISH_STOLLARI[this.rol];
    this.x = stol ? stol.otirish[0] : 2;
    this.y = stol ? stol.otirish[1] : 2;
    this.qaray = 'past';
    this.yol = [];
    this.qadam = 0;      // 0..1 oraliqdagi harakat
    this.animatsiya = 0;
    this.otirgan = true;
    this.holat = null;
    this.maqsad = null;
    this.keyingiSayr = performance.now() + 3000 + Math.random() * 6000;
    this.majlisJoyi = null;    // yig'ilishda o'ziga biriktirilgan o'rindiq
    this.tushlikda = false;    // oshxonaga ketyapti yoki o'tiribdi
    this.tushlikTugashi = 0;   // 0 dan katta bo'lsa — stolga o'tirib bo'ldi
    bandBelgila(this.rol, [this.x, this.y]);   // boshlang'ich katakni egallaydi
  }

  get ofisdami() {
    return this.malumot.amalga_oshirilgan;
  }

  holatRangi() {
    if (this.holat === 'tugadi') return HOLAT_RANGI_OFIS.tugadi;
    if (this.holat === 'tasdiq_kutilmoqda') return HOLAT_RANGI_OFIS.tasdiq_kutilmoqda;
    if (this.holat === 'aniqlik_kerak') return HOLAT_RANGI_OFIS.aniqlik_kerak;
    if (this.holat === 'xato') return HOLAT_RANGI_OFIS.xato;
    if (this.holat === 'ishlayapti') return HOLAT_RANGI_OFIS.ishlayapti;
    return HOLAT_RANGI_OFIS.bosh;
  }

  holatMatni() {
    if (!this.ofisdami) return 'ofisda yo‘q';
    if (this.holat === 'ishlayapti') return 'ishlayapti';
    return HOLAT_MATNI[this.holat] || 'bo‘sh';
  }

  boradi(nishon) {
    if (!nishon) return;
    const hozir = [Math.round(this.x), Math.round(this.y)];
    if (hozir[0] === nishon[0] && hozir[1] === nishon[1]) return;
    const yol = yolTop(hozir, nishon, this.rol);
    if (yol.length) {
      this.yol = yol;
      this.qadam = 0;
      this.otirgan = false;
      this.maqsad = nishon;
    }
  }

  // Holat o'zgarganda xatti-harakat (topshiriq 4.2 jadvali).
  //
  // Majlisga yakka o'zi bormaydi: savol chiqsa BUTUN jamoa yig'iladi va
  // buni `majlisdami()` boshqaradi (`yangila` ichida tekshiriladi).
  holatniQoy(yangi, majlisJoyi) {
    this.majlisJoyi = majlisJoyi || this.majlisJoyi;
    if (yangi === this.holat) return;
    this.holat = yangi;

    if (majlisdami()) return;   // yig'ilish ustuvor — stolga qaytmaydi
    const stol = ISH_STOLLARI[this.rol];
    if (yangi === 'ishlayapti' || yangi === 'tugadi' || yangi === 'xato') {
      if (stol) this.boradi(stol.otirish); // stolga qaytadi
    }
    if (yangi === 'tugadi') this.belgiVaqti = performance.now();
  }

  yangila(dt) {
    if (this.yol.length) {
      // Qadam boshlanishida keyingi katakni bron qilamiz. Agar hamkasbi
      // undan oldin egallab olgan bo'lsa — yo'lni qaytadan hisoblab,
      // atrofidan aylanib o'tamiz.
      if (this.qadam === 0) {
        const [bx, by] = this.yol[0];
        if (bandmi(bx, by, this.rol)) {
          this.yol = this.maqsad
            ? yolTop([this.x, this.y], this.maqsad, this.rol)
            : [];
          if (!this.yol.length) {
            this.keyingiSayr = performance.now() + 800;   // biroz kutamiz
            return;
          }
        }
        bandBelgila(this.rol, [this.x, this.y], this.yol[0]);
      }

      const [nx, ny] = this.yol[0];
      // Majlisga shoshilishadi — ofis kattaligi ~50 katak, oddiy tezlikda
      // eng uzoqdagi agent yarim daqiqa yurardi.
      this.qadam += dt * (majlisdami() ? YURISH_TEZLIGI * 2.1 : YURISH_TEZLIGI);
      if (this.qadam >= 1) {
        this.x = nx;
        this.y = ny;
        bandBelgila(this.rol, [nx, ny]);
        this.qadam = 0;
        this.yol.shift();
        if (!this.yol.length) this._joyigaOtir();
      } else {
        const dx = nx - this.x;
        const dy = ny - this.y;
        if (Math.abs(dx) > Math.abs(dy)) this.qaray = dx > 0 ? 'ong' : 'chap';
        else if (dy !== 0) this.qaray = dy > 0 ? 'past' : 'yuqori';
      }
      this.animatsiya += dt * (majlisdami() ? 17 : 8);   // shoshilsa qadam tez
    } else {
      this.animatsiya = 0;

      // YIG'ILISH — savol chiqqanda hamma majlis xonasiga boradi va
      // o'z o'rindig'ida kutadi. Boshqa hech qayerga ketmaydi.
      if (majlisdami()) {
        if (this.majlisJoyi
            && (this.x !== this.majlisJoyi[0] || this.y !== this.majlisJoyi[1])) {
          this.boradi(this.majlisJoyi);
        } else {
          this.qaray = this.y < 33 ? 'past' : 'yuqori';   // stolga qaraydi
          this.otirgan = true;
        }
        return;
      }

      if (performance.now() < this.keyingiSayr) return;

      // Tushlikda: yetib borgan bo'lsa `tushlikTugashi` qo'yiladi
      // (`_joyigaOtir` ichida) — vaqt STOLGA O'TIRGANDAN keyin sanaladi,
      // yo'lda yurgan vaqt hisobga olinmaydi.
      if (this.tushlikda) {
        if (!this.tushlikTugashi) return;                  // hali yo'lda
        if (performance.now() < this.tushlikTugashi) return;  // ovqatlanyapti
        this.tushlikda = false;
        this.tushlikTugashi = 0;
        this.boradi(ozXonaJoyi(this.rol));
        // Yo'l topilmasa (joy band) darrov qayta urinsin — oshxonada
        // bekorga o'tirib qolmasin.
        this.keyingiSayr = performance.now() + (this.yol.length ? 2000 : 250);
        return;
      }

      if (this.holat === 'ishlayapti') {
        // ISHLAYOTGANDA ikki xil manzara:
        //   ~55% — o'z kompyuteri oldida o'tirib ishlaydi;
        //   qolgani — boshqa bo'limga borib ma'lumot yig'adi.
        // Faqat yurib yursa ham, faqat o'tirsa ham jonsiz ko'rinadi.
        const stol = ISH_STOLLARI[this.rol];
        if (stol && Math.random() < 0.55) {
          this.keyingiSayr = performance.now() + 6000 + Math.random() * 7000;
          this.boradi(stol.otirish);
        } else {
          this.keyingiSayr = performance.now() + 2600 + Math.random() * 3000;
          this.boradi(begonaXonaJoyi(this.rol));
        }
      } else if (!this.holat || this.holat === 'bosh') {
        this.keyingiSayr = performance.now() + 5000 + Math.random() * 8000;
        // Vaqti-vaqti bilan oshxonaga tushlikka chiqadi.
        if (Math.random() < 0.18) {
          const joy = tushlikJoyi();
          if (joy) {
            this.boradi(joy);
            if (this.yol.length) {
              this.tushlikda = true;
              return;
            }
          }
        }
        // Aks holda o'z xonasidan chiqmaydi.
        this.boradi(ozXonaJoyi(this.rol));
      }
    }
  }

  // Manzilga yetib borgach: bu o'rindiqmi? Ish stoli, majlis stuli va
  // oshxona stuli — uchalasida ham o'tiradi va stolga qarab buriladi.
  _joyigaOtir() {
    const stol = ISH_STOLLARI[this.rol];
    if (stol && this.x === stol.otirish[0] && this.y === stol.otirish[1]) {
      this.otirgan = true;
      this.qaray = 'yuqori';          // monitorga qaraydi
      return;
    }
    if (MAJLIS_JOYLARI.some(([x, y]) => x === this.x && y === this.y)) {
      this.otirgan = true;
      this.qaray = this.y < 33 ? 'past' : 'yuqori';   // majlis stoliga
      return;
    }
    const osh = OSH_STOLLARI.find(
      ([x, y]) => Math.abs(x - this.x) + Math.abs(y - this.y) === 1,
    );
    if (osh && this.tushlikda) {
      this.otirgan = true;
      // Ovqatlanish vaqti aynan shu paytdan boshlanadi.
      if (!this.tushlikTugashi) {
        this.tushlikTugashi = performance.now() + 12000 + Math.random() * 10000;
      }
      if (osh[0] !== this.x) this.qaray = osh[0] > this.x ? 'ong' : 'chap';
      else this.qaray = osh[1] > this.y ? 'past' : 'yuqori';
      return;
    }
    this.otirgan = false;
  }

  // Stol atrofidagi yaqin katak (ishlayotganda qisqa yurish uchun).
  _yaqinJoy([x, y]) {
    const nomzodlar = [[x - 2, y], [x + 2, y], [x, y + 2], [x - 1, y + 1], [x + 1, y + 1]];
    const mos = nomzodlar.filter(([nx, ny]) => yuribBoladi(nx, ny));
    return mos.length ? mos[Math.floor(Math.random() * mos.length)] : null;
  }

  // Ekrandagi joyi (dunyo koordinatasida, piksel)
  joylashuv() {
    let x = this.x;
    let y = this.y;
    if (this.yol.length) {
      const [nx, ny] = this.yol[0];
      x += (nx - this.x) * this.qadam;
      y += (ny - this.y) * this.qadam;
    }
    return { px: x * KATAK, py: y * KATAK };
  }
}

// --- sahna -------------------------------------------------------------------


export {
  KATAK, XARITA_ENI, XARITA_BOYI,
  POL, DEVOR, STOL, OSIMLIK, MAJLIS, OSHXONA, GILAM, SHKAF, BEZAK,
  BEZAKLAR, DEVOR_BEZAKLARI,
  BOLIMLAR, ISH_STOLLARI, MAJLIS_JOYLARI, SAYR_JOYLARI, OSIMLIK_JOYLARI,
  OSH_STOL, OSH_STOLLARI, OSHXONA_JOYLARI,
  XARITA, bolimTop, yuribBoladi, yolTop, OfisAgenti,
  bandBelgila, bandmi, bolimJoyi, ozXonaJoyi, begonaXonaJoyi,
  majlisniBoshla, majlisniTugat, majlisdami, majlisOrindigi, tushlikJoyi,
};
