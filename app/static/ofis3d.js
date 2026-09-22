// Ofis — 3D ko'rinish (Three.js, lokal fayl; CDN'ga bog'lanmaydi).
//
// Geometriya `ofis-model.js` dagi XARITADAN quriladi: bir manba, ikki
// ko'rinish. Agentlarning yurishi ham o'sha moduldagi mantiq bilan —
// shuning uchun 3D va 2D bir xil harakat qiladi.

import * as THREE from './vendor/three.module.js';
import {
  BEZAKLAR,
  BOLIMLAR,
  DEVOR,
  DEVOR_BEZAKLARI,
  HOLAT_RANGI_OFIS,
  ISH_STOLLARI,
  JINS,
  MAJLIS_JOYLARI,
  OSH_STOLLARI,
  KIYIM,
  SOCH,
  MAJLIS,
  OfisAgenti,
  OSHXONA,
  OSIMLIK,
  SHKAF,
  STOL,
  XARITA,
  XARITA_BOYI,
  XARITA_ENI,
  XAVF_RANGI_OFIS,
  bolimTop,
  majlisOrindigi,
  majlisdami,
  majlisniBoshla,
  majlisniTugat,
  yuribBoladi,
} from './ofis-model.js';

// Bitta katak = 1 dunyo birligi. Balandliklar shu o'lchovda.
// Devor odamdan BALAND bo'lishi kerak. Figura ~1.95 birlik bo'yida,
// devor esa 1.6 edi — xodimlar devordan oshib turardi va ofis xonaga
// emas, past to'siqli "kabinka"ga o'xshardi. 2.25 — odamdan baland,
// lekin tepadan qaraganda xonaning ichi hamon ko'rinadigan balandlik.
const DEVOR_BALANDLIGI = 2.25;

// MEBEL BALANDLIGI FIGURAGA QARAB tanlangan, teskarisi emas.
//
// Bu yerdagi odam ~1.45 birlik bo'yida va multfilm proporsiyasida —
// oyog'i haqiqiy odamnikiga nisbatan kalta. Mebel esa avval boshqa
// o'lchamga sozlangan edi, natijada o'tirgan agentning oyog'i polga
// yetmay havoda osilib turardi.
//
// Hisob: o'tirganda son gorizontal, boldir tik. Tizzadan tovongacha
// ~0.25 birlik (figura ichida), o'lchamga ko'paytirilsa ~0.36. Demak
// o'tirgich usti ham shu balandlikda bo'lishi kerak — o'shanda tovon
// aynan polga tegadi.
const STUL_USTI = 0.365;
// Stol o'tirgan odamning tirsagidan bir oz past.
const STOL_BALANDLIGI = 0.52;
// Majlis stoli — o'sha stullar atrofida turadi, shuning uchun u ham
// past. Ilgari 0.72 edi: o'tirganlarning ko'kragiga kelardi.
const MAJLIS_BALANDLIGI = 0.55;

// Figura o'lchami. Model bir birlik bo'yida qurilgan (~1 dunyo birligi),
// bu esa mebel yoniga qo'yilganda kichkina chiqadi — shuning uchun
// kattalashtiriladi. Tanlangan agent yana bir oz yiriklashadi.
const FIGURA_OLCHAMI = 1.45;
const FIGURA_TANLANGAN = 1.7;

// PALITRA — "Pixar" ko'rinishi uchun qayta tanlangan (2026-09-09).
//
// Oldingi palitra deyarli monoxrom edi: hamma narsa bir xil bej
// tusda, fon esa qora. Natijada ofis yassi va xira ko'rinardi —
// bo'limlar bir-biridan ajralmasdi, chuqurlik sezilmasdi.
//
// Uch tamoyil:
//   1) TO'YINGAN va AJRALGAN rang — har bo'lim o'z tusiga ega;
//   2) YORUG' fon — qora emas, iliq osmon tusi. Qora fon sahnani
//      "kesib" tashlaydi va kayfiyatni tushiradi;
//   3) QIYMAT FARQI — pol yorug', mebel to'q, shunda shakl ko'rinadi.
const RANG = {
  yolak: 0xe8dcc8,
  // Devor deyarli oq (0xfff6e8) edi — ACES ostida u oqarib ketib,
  // bo'sh qog'ozga o'xshab qolardi. Bir oz to'q krem tus soya va
  // yorug'lik farqini ushlab turadi.
  devor: 0xf2ddc0,
  devorTepa: 0xf0e2cd,
  stol: 0xc97f45,
  stolUst: 0xe8a866,
  monitor: 0x2b3038,
  monitorYoniq: 0x7fd4f0,
  osimlik: 0x4fae52,
  tuvak: 0xe0663c,
  majlis: 0xd08a4a,
  oshxona: 0xf0d9a8,
  shkaf: 0xa9713f,
  teri: 0xe8b088,
  divan: 0x6f8ba8,        // ko'kimtir mato — iliq polga qarshi salqin dog'
  divanYostiq: 0xe0a45c,  // yostiqlar to'q sariq: divanda diqqat nuqtasi
  doska: 0xf4f6f4,
  ramkaYogoch: 0x8a5a34,
  // Iliq osmon tusi — sahna atrofi "havo" bo'lib ko'rinadi.
  fon: 0xbfd9e8,
};

function rangdan(matn) {
  return new THREE.Color(matn || '#888888');
}

// --- yumaloq qirrali quti ----------------------------------------------------
//
// `BoxGeometry` ning qirralari ideal 90° — yorug'lik ularda BIRDANIGA
// uziladi va predmet "karton" bo'lib ko'rinadi. Haqiqiy jihozning
// qirrasi esa yumaloq: shu ingichka yuza yorug'likni ushlab, chetda
// yorug' chiziq beradi. Multfilm renderining eng sezilarli belgisi —
// aynan shu.
//
// `three.module.js` yalang'och yadro (RoundedBoxGeometry qo'shimchalarda
// keladi), shuning uchun o'zimiz quramiz: yumaloq to'rtburchakni
// cho'zamiz va uchlariga fasqa (bevel) beramiz.
//
// Natija `BoxGeometry(en, boy, chuq)` bilan bir xil joylashadi.
const QUTI_KESHI = new Map();

function yumaloqQuti(en, boy, chuq, radius = 0.05, fasqa = 0.02) {
  const kalit = [en, boy, chuq, radius, fasqa].join(':');
  if (QUTI_KESHI.has(kalit)) return QUTI_KESHI.get(kalit);

  // Fasqa yarim o'lchamdan katta bo'lsa geometriya ichiga qarab
  // buriladi (yupqa predmetlarda — masalan monitor korpusida).
  const f = Math.min(fasqa, en / 2.5, boy / 2.5, chuq / 2.5);
  const yarimEn = en / 2 - f;
  const yarimChuq = chuq / 2 - f;
  const r = Math.min(radius, yarimEn * 0.98, yarimChuq * 0.98);

  const shakl = new THREE.Shape();
  shakl.moveTo(-yarimEn + r, -yarimChuq);
  shakl.lineTo(yarimEn - r, -yarimChuq);
  shakl.quadraticCurveTo(yarimEn, -yarimChuq, yarimEn, -yarimChuq + r);
  shakl.lineTo(yarimEn, yarimChuq - r);
  shakl.quadraticCurveTo(yarimEn, yarimChuq, yarimEn - r, yarimChuq);
  shakl.lineTo(-yarimEn + r, yarimChuq);
  shakl.quadraticCurveTo(-yarimEn, yarimChuq, -yarimEn, yarimChuq - r);
  shakl.lineTo(-yarimEn, -yarimChuq + r);
  shakl.quadraticCurveTo(-yarimEn, -yarimChuq, -yarimEn + r, -yarimChuq);

  const geo = new THREE.ExtrudeGeometry(shakl, {
    depth: Math.max(boy - f * 2, 0.001),
    bevelEnabled: true,
    bevelThickness: f,
    bevelSize: f,
    bevelSegments: 2,
    curveSegments: 6,
  });
  // Cho'zish +Z bo'ylab ketadi; uni +Y ga o'giramiz va markazlaymiz.
  geo.translate(0, 0, -(boy / 2) + f);
  geo.rotateX(-Math.PI / 2);
  geo.computeVertexNormals();

  QUTI_KESHI.set(kalit, geo);
  return geo;
}

// --- protsedura teksturalar --------------------------------------------------
//
// Tashqi rasm fayli yo'q (CDN'ga bog'lanmaymiz). Kichik kanvasga naqsh
// chizib, uni takrorlanadigan tekstura qilamiz: tekis rangli yuza
// plastmassaga o'xshaydi, mayda naqsh esa materialni "tirik" qiladi.

const TEKSTURA_KESHI = new Map();

// Kanvas faqat CSS rangni tushunadi. Xarita ranglari esa ikki xil keladi:
// '#e8d8b8' (bo'lim) va 0xcbb99b (son). Ikkalasini ham bir ko'rinishga
// keltiramiz — aks holda `fillStyle` jimgina e'tiborsiz qoladi va
// tekstura qora chiqadi.
function css(rang) {
  return '#' + new THREE.Color(rang).getHexString();
}

function teksturaYasa(kalit, chizuvchi, olcham = 128) {
  if (TEKSTURA_KESHI.has(kalit)) return TEKSTURA_KESHI.get(kalit);
  const kanvas = document.createElement('canvas');
  kanvas.width = olcham;
  kanvas.height = olcham;
  chizuvchi(kanvas.getContext('2d'), olcham);
  const t = new THREE.CanvasTexture(kanvas);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  TEKSTURA_KESHI.set(kalit, t);
  return t;
}

// Gilam — mayda tolali to'qima.
function gilamTeksturasi(tus) {
  return teksturaYasa(`gilam:${tus}`, (k, n) => {
    k.fillStyle = tus;
    k.fillRect(0, 0, n, n);
    for (let i = 0; i < n * 34; i++) {
      const x = Math.random() * n;
      const y = Math.random() * n;
      const yorqin = Math.random() < 0.5;
      k.fillStyle = yorqin ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
      k.fillRect(x, y, 1.6, 1);
    }
  });
}

// Yo'lak — parket taxtalari.
function parketTeksturasi(tus) {
  return teksturaYasa(`parket:${tus}`, (k, n) => {
    k.fillStyle = tus;
    k.fillRect(0, 0, n, n);
    const taxta = n / 4;
    for (let qator = 0; qator < 4; qator++) {
      const surish = (qator % 2) * (taxta / 2);
      k.fillStyle = `rgba(0,0,0,${0.05 + qator * 0.012})`;
      k.fillRect(0, qator * taxta, n, taxta);
      // Tolalar
      for (let i = 0; i < 26; i++) {
        k.fillStyle = Math.random() < 0.5
          ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.07)';
        k.fillRect(Math.random() * n, qator * taxta + Math.random() * taxta,
          6 + Math.random() * 14, 1);
      }
      // Ko'ndalang chok
      k.fillStyle = 'rgba(0,0,0,0.22)';
      k.fillRect(surish, qator * taxta, 1.2, taxta);
      k.fillRect((surish + n / 2) % n, qator * taxta, 1.2, taxta);
      k.fillRect(0, qator * taxta, n, 1);
    }
  });
}

// Devor — mayda donador shpaklyovka.
function devorTeksturasi(tus) {
  return teksturaYasa(`devor:${tus}`, (k, n) => {
    k.fillStyle = tus;
    k.fillRect(0, 0, n, n);
    for (let i = 0; i < n * 12; i++) {
      k.fillStyle = Math.random() < 0.5
        ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.045)';
      k.fillRect(Math.random() * n, Math.random() * n, 1, 1);
    }
  }, 64);
}

// Yog'och — stol usti uchun tolali naqsh.
function yogochTeksturasi(tus) {
  return teksturaYasa(`yogoch:${tus}`, (k, n) => {
    k.fillStyle = tus;
    k.fillRect(0, 0, n, n);
    for (let i = 0; i < 90; i++) {
      k.strokeStyle = Math.random() < 0.5
        ? 'rgba(255,255,255,0.06)' : 'rgba(60,30,10,0.14)';
      k.lineWidth = 0.6 + Math.random();
      const y = Math.random() * n;
      k.beginPath();
      k.moveTo(0, y);
      k.bezierCurveTo(n / 3, y + (Math.random() - 0.5) * 5,
        (n / 3) * 2, y + (Math.random() - 0.5) * 5, n, y);
      k.stroke();
    }
  });
}

// Marker doskasi — oq yuza, ustida sxema va bir necha qator "yozuv".
// Aniq matn kerak emas: uzoqdan baribir o'qilmaydi, lekin doska bo'sh
// bo'lsa ishlatilmayotgandek ko'rinadi.
function doskaTeksturasi() {
  return teksturaYasa('doska', (k, n) => {
    k.fillStyle = '#f6f8f7';
    k.fillRect(0, 0, n, n);

    // Yengil ko'kimtir dog'lar — o'chirilgan marker izi.
    for (let i = 0; i < 5; i++) {
      k.fillStyle = 'rgba(150,170,180,0.08)';
      k.fillRect(Math.random() * n, Math.random() * n, 18 + Math.random() * 30, 8);
    }

    // Chap tomonda — quti va strelkali sxema.
    k.strokeStyle = '#3f6f9e';
    k.lineWidth = 2.4;
    k.strokeRect(n * 0.08, n * 0.16, n * 0.22, n * 0.16);
    k.strokeRect(n * 0.08, n * 0.5, n * 0.22, n * 0.16);
    k.beginPath();
    k.moveTo(n * 0.19, n * 0.32);
    k.lineTo(n * 0.19, n * 0.5);
    k.stroke();

    // O'ng tomonda — qator-qator "matn".
    k.strokeStyle = '#c0453a';
    k.lineWidth = 2;
    for (let i = 0; i < 6; i++) {
      const y = n * 0.2 + i * n * 0.1;
      k.beginPath();
      k.moveTo(n * 0.4, y);
      k.lineTo(n * (0.55 + Math.random() * 0.32), y);
      k.stroke();
    }
  }, 256);
}

// Devordagi surat — abstrakt manzara: osmon, quyosh va tepaliklar.
// Har ramkaga o'z tusi beriladi, shuning uchun ular takrorlanmaydi.
function suratTeksturasi(tus) {
  return teksturaYasa(`surat:${tus}`, (k, n) => {
    const asos = new THREE.Color(tus);
    const osmon = asos.clone().offsetHSL(0, -0.25, 0.3);
    k.fillStyle = '#' + osmon.getHexString();
    k.fillRect(0, 0, n, n);

    k.fillStyle = 'rgba(255,240,200,0.85)';
    k.beginPath();
    k.arc(n * 0.7, n * 0.28, n * 0.1, 0, Math.PI * 2);
    k.fill();

    // Ikki qatlam tepalik — orqadagisi ochroq, oldingisi to'q.
    [[0.62, -0.06], [0.78, 0.1]].forEach(([balandlik, farq], i) => {
      const tepa = asos.clone().offsetHSL(0, 0.05, farq);
      k.fillStyle = '#' + tepa.getHexString();
      k.beginPath();
      k.moveTo(0, n);
      k.lineTo(0, n * balandlik);
      for (let x = 0; x <= n; x += n / 8) {
        k.lineTo(x, n * balandlik + Math.sin(x / n * Math.PI * (2 + i)) * n * 0.07);
      }
      k.lineTo(n, n);
      k.closePath();
      k.fill();
    });
  }, 128);
}

// --- yorliq (matnni tekstura sifatida chizamiz) ------------------------------

function yorliqYasa(matn, tus = '#f2ece2', olcham = 44, kenglik = 120, uslub = 'ism') {
  // Ikki xil yorliq bir-biriga o'xshab ketmasligi kerak:
  //   XONA — katta harflar, sarg'ish, ramkasiz, xira fon;
  //   ISM  — oddiy harflar, oq, rangli ramka bilan.
  const xonami = uslub === 'xona';
  const yozuv = xonami ? matn.toUpperCase() : matn;
  const shrift = xonami
    ? `700 ${olcham}px system-ui, sans-serif`
    : `600 ${olcham}px system-ui, sans-serif`;

  // XONA yorlig'ida harflar orasi kengaytiriladi. Buni O'LCHASHDAN OLDIN
  // qo'yish shart: ilgari `letterSpacing` o'lchagandan keyin berilardi,
  // shuning uchun kanvas (n-1)*3px tor chiqib, bo'lim nomining oxirgi
  // harflari kesilib qolardi.
  const harfOraligi = xonami ? '3px' : '0px';

  const kanvas = document.createElement('canvas');
  const ktx = kanvas.getContext('2d');
  ktx.font = shrift;
  ktx.letterSpacing = harfOraligi;
  const chetlash = xonami ? 26 : 16;
  kanvas.width = Math.ceil(ktx.measureText(yozuv).width) + chetlash * 2;
  kanvas.height = olcham + (xonami ? 22 : 26);

  // `canvas.width` ga yozish kontekstni nolga qaytaradi — qayta qo'yamiz.
  const k2 = kanvas.getContext('2d');
  k2.font = shrift;
  k2.letterSpacing = harfOraligi;
  k2.fillStyle = xonami ? 'rgba(28,22,16,0.42)' : 'rgba(16,14,12,0.82)';
  k2.roundRect(0, 0, kanvas.width, kanvas.height, xonami ? 6 : 13);
  k2.fill();
  if (!xonami) {
    k2.strokeStyle = tus;
    k2.lineWidth = 3;
    k2.roundRect(1.5, 1.5, kanvas.width - 3, kanvas.height - 3, 12);
    k2.stroke();
  }
  k2.fillStyle = xonami ? '#f6dfae' : '#f6f2ea';
  k2.textBaseline = 'middle';
  k2.fillText(yozuv, chetlash, kanvas.height / 2);

  const tekstura = new THREE.CanvasTexture(kanvas);
  tekstura.colorSpace = THREE.SRGBColorSpace;
  const sprayt = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: tekstura, depthTest: false, transparent: true }),
  );
  // `kenglik` — 1 dunyo birligiga to'g'ri keladigan piksel soni.
  // Kichik qiymat yorliqni kattalashtiradi va sahnani bosib ketadi.
  sprayt.scale.set(kanvas.width / kenglik, kanvas.height / kenglik, 1);
  sprayt.renderOrder = 10;
  return sprayt;
}

// --- 3D agent ----------------------------------------------------------------

// Gavda o'lchamlari. Erkak kengroq yelkali va bir oz baland, ayolning
// beli ingichka va yelkasi tor — siluetdan uzoqdan ham farqlanadi.
const GAVDA = {
  erkak: {
    yelka: 0.25, bel: 0.20, boy: 0.46, oyoqOraligi: 0.10,
    qolQalinligi: 0.055, boyi: 1.0, etakli: false,
  },
  ayol: {
    yelka: 0.19, bel: 0.155, boy: 0.44, oyoqOraligi: 0.075,
    qolQalinligi: 0.045, boyi: 0.94, etakli: true,
  },
};

// Bo'g'im: qo'l/oyoq o'z markazidan emas, YELKA va CHANOQdan aylanadi.
// Shuning uchun mesh pivotdan pastga siljitilib qo'yiladi.
function bogim(mesh, uzunlik) {
  const pivot = new THREE.Group();
  mesh.position.y = -uzunlik / 2;
  pivot.add(mesh);
  return pivot;
}

// Aylanma gavda: profil nuqtalaridan silliq jism yasaydi.
//
// Silindr yoki konus tananing egri chizig'ini bermaydi — yelka, ko'krak,
// bel va chanoq bitta uzluksiz yuzada bo'lishi kerak. `LatheGeometry`
// shu profilni o'q atrofida aylantiradi va normallar silliq chiqadi.
function gavdaGeometriyasi(nuqtalar, segment = 22) {
  const profil = nuqtalar.map(([r, y]) => new THREE.Vector2(Math.max(r, 0.001), y));
  const geo = new THREE.LatheGeometry(profil, segment);
  geo.computeVertexNormals();
  return geo;
}

// Ikki radius orasini yumshoq o'tkazadi (profil nuqtalarini zichlash uchun).
function egriProfil(bosqichlar, qadam = 5) {
  const chiq = [];
  for (let i = 0; i < bosqichlar.length - 1; i++) {
    const [r0, y0] = bosqichlar[i];
    const [r1, y1] = bosqichlar[i + 1];
    for (let j = 0; j < qadam; j++) {
      const t = j / qadam;
      // Kosinus interpolyatsiya — burchaksiz, tabiiy o'tish.
      const s = (1 - Math.cos(t * Math.PI)) / 2;
      chiq.push([r0 + (r1 - r0) * s, y0 + (y1 - y0) * s]);
    }
  }
  chiq.push(bosqichlar[bosqichlar.length - 1]);
  return chiq;
}

class Agent3D {
  constructor(agent) {
    this.agent = agent;
    this.guruh = new THREE.Group();

    const tus = rangdan(KIYIM[agent.rol]);
    const jins = JINS[agent.rol] === 'ayol' ? 'ayol' : 'erkak';
    const o = GAVDA[jins];
    this.jins = jins;

    // Teri va soch ranglari bir xil bo'lib qolmasin — rol nomidan
    // barqaror "tasodif" olamiz (har yuklashda o'zgarmasin).
    const urug = [...agent.rol].reduce((s, c) => s + c.charCodeAt(0), 0);
    const teriTus = new THREE.Color(RANG.teri).offsetHSL(
      ((urug % 7) - 3) * 0.004, ((urug % 5) - 2) * 0.03, ((urug % 9) - 4) * 0.016,
    );

    const kiyimMat = new THREE.MeshStandardMaterial({
      color: tus, roughness: 0.86, metalness: 0,
    });
    const teriMat = new THREE.MeshStandardMaterial({
      color: teriTus, roughness: 0.62, metalness: 0,
    });
    // Shim rangi ko'ylakdan olinadi: to'q va kamroq to'yingan tus.
    // Ilgari hammada bir xil qoramtir ko'k (0x38404d) edi — uzoqdan
    // qaraganda figuralarning pastki yarmi bir xil qora dog' bo'lib
    // qo'shilib ketardi. Endi har kishi butunligicha o'z rangida.
    const shimMat = new THREE.MeshStandardMaterial({
      color: tus.clone().offsetHSL(0.015, -0.26, -0.28),
      roughness: 0.88, metalness: 0,
    });
    const poyabzalMat = new THREE.MeshStandardMaterial({
      color: 0x231e1b, roughness: 0.42, metalness: 0.05,
    });
    const sochMat = new THREE.MeshStandardMaterial({
      color: SOCH[agent.rol] ?? 0x33261d, roughness: 0.72, metalness: 0.04,
    });

    // Bir xil bo'yli 12 kishi g'alati ko'rinadi — ±4% farq beramiz.
    const boyFarqi = 1 + ((urug % 11) - 5) * 0.008;
    const chanoq = 0.50 * o.boyi * boyFarqi;   // oyoq boshlanadigan balandlik
    const yelkaB = 0.92 * o.boyi * boyFarqi;   // yelka balandligi
    // O'tirganda gavdani stulga tushirish uchun kerak (pastga qarang).
    this.chanoq = chanoq;

    // --- Tana: aylanma profil (yelka -> ko'krak -> bel -> chanoq) -----------
    // Silindr yoki konus emas: profil egri chizig'i tanani odamga
    // o'xshatadi. Ayolda ko'krak va chanoq kengroq, bel ingichka.
    const past = chanoq - 0.02;
    const ust = yelkaB + 0.03;
    const h = ust - past;
    const profil = o.etakli
      ? [
        [0.001, past], [o.bel * 1.12, past], [o.bel * 1.16, past + h * 0.14],
        [o.bel * 0.93, past + h * 0.42], [o.yelka * 1.03, past + h * 0.72],
        [o.yelka, past + h * 0.9], [o.yelka * 0.74, ust], [0.001, ust],
      ]
      : [
        [0.001, past], [o.bel * 1.04, past], [o.bel * 1.02, past + h * 0.2],
        [o.bel * 1.06, past + h * 0.46], [o.yelka * 1.02, past + h * 0.78],
        [o.yelka, past + h * 0.92], [o.yelka * 0.78, ust], [0.001, ust],
      ];
    this.tana = new THREE.Mesh(gavdaGeometriyasi(egriProfil(profil, 4)), kiyimMat);
    this.tana.castShadow = true;
    this.tana.receiveShadow = true;
    this.guruh.add(this.tana);
    // Aylanish markazini bel balandligiga olamiz (engashish shu yerdan).
    this.tana.geometry.translate(0, -past - h * 0.4, 0);
    this.tana.position.y = past + h * 0.4;

    // Yelka uchlari — qo'l ulanadigan joy yumaloq bo'lsin.
    [-1, 1].forEach((tomon) => {
      const uchi = new THREE.Mesh(new THREE.SphereGeometry(o.yelka * 0.42, 12, 10), kiyimMat);
      uchi.scale.set(1, 0.85, 1);
      uchi.position.set(tomon * o.yelka * 0.82, yelkaB - 0.02, 0);
      uchi.castShadow = true;
      this.guruh.add(uchi);
    });

    // Ayol uchun etak — chanoqdan pastga silliq kengayadi
    if (o.etakli) {
      const etak = new THREE.Mesh(
        gavdaGeometriyasi(egriProfil([
          [o.bel * 1.1, past + 0.02], [o.bel * 1.5, past - 0.12],
          [o.yelka * 1.5, past - 0.24], [0.001, past - 0.25],
        ], 4)),
        kiyimMat,
      );
      etak.material.side = THREE.DoubleSide;
      etak.castShadow = true;
      this.guruh.add(etak);
    }

    // --- Qo'llar: YELKA va TIRSAK ikki bo'g'im ------------------------------
    // Bitta bo'g'im bilan o'tirgan odamning qo'li taxtadek oldinga
    // cho'ziladi. Tirsak qo'shilgach, klaviaturaga qo'l qo'yish mumkin.
    const A = 0.34 * o.boyi * boyFarqi;
    this.qollar = [-1, 1].map((tomon) => {
      const yelkaPivot = new THREE.Group();

      const yeng = new THREE.Mesh(
        new THREE.CapsuleGeometry(o.qolQalinligi, A * 0.3, 4, 10), kiyimMat,
      );
      yeng.position.y = -A * 0.23;
      yeng.castShadow = true;

      const tirsak = new THREE.Group();
      tirsak.position.y = -A * 0.46;

      // Bilak — yengdan ingichkaroq va teri rangida (kalta yeng effekti).
      const bilak = new THREE.Mesh(
        new THREE.CapsuleGeometry(o.qolQalinligi * 0.8, A * 0.26, 4, 10), teriMat,
      );
      bilak.position.y = -A * 0.22;
      bilak.castShadow = true;

      const panja = new THREE.Mesh(new THREE.SphereGeometry(o.qolQalinligi * 1.05, 10, 8), teriMat);
      panja.scale.set(0.8, 1.2, 0.65);
      panja.position.y = -A * 0.45;
      tirsak.add(bilak, panja);

      yelkaPivot.add(yeng, tirsak);
      yelkaPivot.position.set(tomon * (o.yelka * 0.92 + o.qolQalinligi), yelkaB - 0.02, 0);
      yelkaPivot.rotation.z = tomon * 0.07;    // qo'llar biroz yon tomonga
      yelkaPivot.userData.tirsak = tirsak;
      this.guruh.add(yelkaPivot);
      return yelkaPivot;
    });

    // --- Oyoqlar: CHANOQ va TIZZA ikki bo'g'im -----------------------------
    const L = chanoq;
    this.oyoqlar = [-1, 1].map((tomon) => {
      const chanoqPivot = new THREE.Group();
      const oyoqMat = o.etakli ? teriMat : shimMat;

      const son = new THREE.Mesh(
        new THREE.CapsuleGeometry(0.068, L * 0.28, 4, 10), oyoqMat,
      );
      son.position.y = -L * 0.25;
      son.castShadow = true;

      const tizza = new THREE.Group();
      tizza.position.y = -L * 0.5;

      const boldir = new THREE.Mesh(
        new THREE.CapsuleGeometry(0.05, L * 0.26, 4, 10), oyoqMat,
      );
      boldir.position.y = -L * 0.23;
      boldir.castShadow = true;

      // Poyabzal: tovon + burun, tekis quti emas.
      const poyabzal = new THREE.Group();
      const taban = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.032, 0.15), poyabzalMat);
      taban.position.z = 0.02;
      const burun = new THREE.Mesh(new THREE.SphereGeometry(0.052, 10, 8), poyabzalMat);
      burun.scale.set(0.95, 0.6, 1.25);
      burun.position.set(0, 0.01, 0.07);
      poyabzal.add(taban, burun);
      poyabzal.position.y = -L * 0.46;
      poyabzal.castShadow = true;
      tizza.add(boldir, poyabzal);

      chanoqPivot.add(son, tizza);
      chanoqPivot.position.set(tomon * o.oyoqOraligi, chanoq, 0);
      chanoqPivot.userData.tizza = tizza;
      this.guruh.add(chanoqPivot);
      return chanoqPivot;
    });

    // --- Kiyim tafsilotlari: yoqa va kamar ----------------------------------
    const yoqa = new THREE.Mesh(
      new THREE.TorusGeometry(0.068, 0.018, 8, 18), kiyimMat,
    );
    yoqa.rotation.x = Math.PI / 2;
    yoqa.position.y = yelkaB + 0.035;
    this.guruh.add(yoqa);

    if (!o.etakli) {
      const kamar = new THREE.Mesh(
        new THREE.CylinderGeometry(o.bel * 1.09, o.bel * 1.09, 0.045, 18),
        new THREE.MeshStandardMaterial({ color: 0x2e2723, roughness: 0.45, metalness: 0.1 }),
      );
      kamar.position.y = chanoq + 0.045;
      this.guruh.add(kamar);
      const toqa = new THREE.Mesh(
        new THREE.BoxGeometry(0.05, 0.038, 0.012),
        new THREE.MeshStandardMaterial({ color: 0xc9ad72, roughness: 0.3, metalness: 0.85 }),
      );
      toqa.position.set(0, chanoq + 0.045, o.bel * 1.09);
      this.guruh.add(toqa);
    }

    // --- Bo'yin, bosh va yuz ------------------------------------------------
    const boyin = new THREE.Mesh(
      gavdaGeometriyasi([[0.062, 0], [0.055, 0.04], [0.058, 0.09]], 12), teriMat,
    );
    boyin.position.y = yelkaB + 0.01;
    this.guruh.add(boyin);

    // Yuz alohida guruhda — agent qaysi tomonga qarasa, ko'z va og'iz
    // ham o'sha tomonga buriladi.
    this.boshGuruh = new THREE.Group();
    this.boshGuruh.position.y = yelkaB + 0.235;
    // Multfilm proporsiyasi: bosh haqiqiy odamnikidan kattaroq.
    // Yuz — qaralayotgan yagona joy, shuning uchun u yirikroq bo'lsa
    // uzoqdan ham kim ekani o'qiladi. Ko'z, soch, burun — hammasi shu
    // guruhning ichida, demak bittasi bilan barchasi kattalashadi.
    this.boshGuruh.scale.setScalar(1.2);
    this.guruh.add(this.boshGuruh);

    // Bosh — sof shar emas: iyak toraygan, ensa to'laroq.
    const bosh = new THREE.Mesh(new THREE.SphereGeometry(0.145, 24, 20), teriMat);
    bosh.scale.set(1, 1.1, 0.95);
    bosh.castShadow = true;
    this.boshGuruh.add(bosh);
    // Iyak va jag' — pastki qismni toraytiradi.
    const jag = new THREE.Mesh(new THREE.SphereGeometry(0.108, 18, 14), teriMat);
    jag.scale.set(1, 0.9, 1.02);
    jag.position.set(0, -0.062, 0.014);
    this.boshGuruh.add(jag);

    // Quloqlar
    [-1, 1].forEach((tomon) => {
      const quloq = new THREE.Mesh(new THREE.SphereGeometry(0.03, 10, 8), teriMat);
      quloq.scale.set(0.42, 1.05, 0.85);
      quloq.position.set(tomon * 0.137, 0.002, -0.004);
      this.boshGuruh.add(quloq);
    });

    // --- Soch --------------------------------------------------------------
    //
    // Yarim shar "kaska" bo'lib turadi. Shuning uchun soch bir necha
    // qismdan yig'iladi: bosh suyagini qoplaydigan qism, peshonadagi
    // to'lqin va (ayolda) yelkaga tushadigan hajm.
    const sochGuruh = new THREE.Group();
    this.boshGuruh.add(sochGuruh);

    // Soch chizig'i qoshdan YUQORIDA tugashi shart. Aks holda soch
    // ko'zni yopib, yuz ko'rinmay qoladi. Qoplama boshga tegib turadi,
    // lekin pastki qirrasi peshonada y ~ 0.09 da.
    const qoplama = new THREE.Mesh(
      new THREE.SphereGeometry(0.152, 24, 18, 0, Math.PI * 2, 0, 1.02),
      sochMat,
    );
    qoplama.scale.set(0.99, 1.07, 0.94);
    qoplama.rotation.x = -0.1;   // old tomoni ko'tariladi, ensa pastroq tushadi
    qoplama.castShadow = true;
    sochGuruh.add(qoplama);

    // Peshona ustidagi to'lqin — soch chizig'i ustida hajm beradi,
    // "kaska" taassurotini yo'qotadi.
    const tolqin = new THREE.Mesh(new THREE.SphereGeometry(0.07, 16, 12), sochMat);
    tolqin.scale.set(1.5, 0.66, 0.6);
    tolqin.position.set(jins === 'ayol' ? -0.022 : 0.016, 0.108, 0.072);
    tolqin.rotation.z = jins === 'ayol' ? 0.24 : -0.13;
    sochGuruh.add(tolqin);

    // Ensa — bo'yin ustidagi hajm (erkakda ham bor, kaltaroq).
    const ensa = new THREE.Mesh(
      gavdaGeometriyasi(egriProfil(jins === 'ayol'
        ? [[0.06, 0.085], [0.142, 0.0], [0.152, -0.15], [0.13, -0.27], [0.02, -0.3]]
        : [[0.06, 0.075], [0.136, -0.005], [0.124, -0.075], [0.055, -0.1]], 4), 18),
      sochMat,
    );
    // Faqat orqa yarmiga hajm beradi — old tomonda yuzni bosmaydi.
    ensa.scale.set(1, 1, 0.58);
    ensa.position.z = -0.042;
    ensa.castShadow = true;
    sochGuruh.add(ensa);

    if (jins === 'ayol') {
      // Yelkaga tushadigan ikki to'p — tekis kapsula emas, hajmli.
      [-1, 1].forEach((tomon) => {
        const tutam = new THREE.Mesh(
          gavdaGeometriyasi(egriProfil([
            [0.028, 0.05], [0.062, -0.04], [0.07, -0.16], [0.045, -0.26], [0.01, -0.29],
          ], 4), 14),
          sochMat,
        );
        tutam.scale.set(1, 1, 0.75);
        tutam.position.set(tomon * 0.108, -0.01, -0.012);
        tutam.rotation.z = tomon * -0.1;
        tutam.castShadow = true;
        sochGuruh.add(tutam);
      });
    }

    // Ko'z yuzning ICHIGA botirilgan — bo'rtib chiqsa qo'g'irchoqqa
    // o'xshab qoladi. Bosh sirti z ~ 0.136 da, ko'z undan orqada.
    const kozMat = new THREE.MeshBasicMaterial({ color: 0x241d19 });
    const oqMat = new THREE.MeshBasicMaterial({ color: 0xefe7dc });
    [-1, 1].forEach((tomon) => {
      const oq = new THREE.Mesh(new THREE.SphereGeometry(0.022, 8, 8), oqMat);
      oq.scale.set(1.05, 0.62, 0.4);
      oq.position.set(tomon * 0.052, 0.018, 0.116);
      this.boshGuruh.add(oq);

      const qorachiq = new THREE.Mesh(new THREE.SphereGeometry(0.0105, 8, 8), kozMat);
      qorachiq.scale.set(1, 1, 0.6);
      qorachiq.position.set(tomon * 0.052, 0.018, 0.125);
      this.boshGuruh.add(qorachiq);

      const qosh = new THREE.Mesh(new THREE.BoxGeometry(0.042, 0.009, 0.01), sochMat);
      qosh.rotation.z = tomon * 0.09;
      qosh.position.set(tomon * 0.052, 0.052, 0.119);
      this.boshGuruh.add(qosh);
    });

    // Burun — yuzga chuqurlik beradi
    const burun = new THREE.Mesh(new THREE.ConeGeometry(0.018, 0.04, 6), teriMat);
    burun.rotation.x = Math.PI / 2;
    burun.position.set(0, -0.012, 0.132);
    this.boshGuruh.add(burun);

    const ogiz = new THREE.Mesh(
      new THREE.BoxGeometry(0.048, 0.011, 0.01),
      new THREE.MeshBasicMaterial({ color: jins === 'ayol' ? 0xa8544f : 0x8d5a4a }),
    );
    ogiz.position.set(0, -0.058, 0.122);
    this.boshGuruh.add(ogiz);

    // Holat nuqtasi — boshdan yuqorida
    this.nuqta = new THREE.Mesh(
      new THREE.SphereGeometry(0.085, 10, 8),
      new THREE.MeshBasicMaterial({ color: 0x8a8175 }),
    );
    this.nuqta.position.y = yelkaB + 0.46;
    this.guruh.add(this.nuqta);

    this.yorliq = yorliqYasa(
      agent.malumot.ism || agent.rol,
      '#' + tus.getHexString(), 34, 96, 'ism',
    );
    this.yorliq.position.y = yelkaB + 0.72;
    this.guruh.add(this.yorliq);

    this.guruh.scale.setScalar(FIGURA_OLCHAMI);
  }

  yangila() {
    const a = this.agent;
    let x = a.x;
    let y = a.y;
    if (a.yol.length) {
      const [nx, ny] = a.yol[0];
      x += (nx - a.x) * a.qadam;
      y += (ny - a.y) * a.qadam;
    }
    this.guruh.position.set(x + 0.5, 0, y + 0.5);

    // Yuzi yurish yo'nalishiga qaraydi.
    const burchak = { yuqori: Math.PI, past: 0, chap: -Math.PI / 2, ong: Math.PI / 2 };
    const nishon = burchak[a.qaray] ?? 0;
    this.guruh.rotation.y += (nishon - this.guruh.rotation.y) * 0.18;

    const yuryapti = a.yol.length > 0;
    const otirgan = a.otirgan && !yuryapti;
    // Ravon o'tish uchun yordamchi: joriy burchakni nishonga yaqinlashtiradi.
    const siljit = (obyekt, oq, nishon, tezlik = 0.16) => {
      obyekt.rotation[oq] += (nishon - obyekt.rotation[oq]) * tezlik;
    };

    if (yuryapti) {
      // Qadam tashlash. Bo'g'imlar yelka/tirsak va chanoq/tizzada,
      // shuning uchun a'zolar odamdek bukiladi: orqaga ketgan oyoq
      // tizzadan bukiladi, oldingisi to'g'rilanadi.
      const t = Math.sin(a.animatsiya * 1.6);
      [0, 1].forEach((i) => {
        const yon = i === 0 ? 1 : -1;
        this.oyoqlar[i].rotation.x = t * yon * 0.6;
        // Tizza faqat bir tomonga bukiladi (orqaga), odamdagidek.
        this.oyoqlar[i].userData.tizza.rotation.x = Math.max(0, t * yon) * 0.75;
        this.qollar[i].rotation.x = -t * yon * 0.45;
        this.qollar[i].userData.tirsak.rotation.x = -0.28 - Math.max(0, -t * yon) * 0.3;
        this.qollar[i].rotation.z = (i === 0 ? 1 : -1) * 0.06;
      });
      // Yurganda gavda sal oldinga engashadi va qadam bilan ko'tariladi.
      this.tana.rotation.x = 0.06;
      this.guruh.position.y = Math.abs(t) * 0.035;
    } else if (otirgan) {
      // O'TIRISH: son gorizontal (oldinga), boldir tik pastga.
      // Kompyuter oldida bo'lsa — qo'l klaviaturada va yozayotgandek
      // mayda harakat qiladi; boshqa joyda — qo'l stolda tinch turadi.
      const stol = ISH_STOLLARI[a.rol];
      const ishStolida = a.holat === 'ishlayapti' && stol
        && a.x === stol.otirish[0] && a.y === stol.otirish[1];
      const yozish = ishStolida ? Math.sin(performance.now() / 120) * 0.06 : 0;

      this.oyoqlar.forEach((oyoq, i) => {
        siljit(oyoq, 'x', -1.45);
        siljit(oyoq.userData.tizza, 'x', 1.42);
        oyoq.rotation.z = (i === 0 ? 1 : -1) * 0.04;
      });
      this.qollar.forEach((qol, i) => {
        siljit(qol, 'x', ishStolida ? -0.42 : -0.3);
        siljit(qol.userData.tirsak, 'x', (ishStolida ? -1.05 : -0.85)
          + (i === 0 ? yozish : -yozish));
        qol.rotation.z = (i === 0 ? 1 : -1) * (ishStolida ? 0.16 : 0.1);
      });
      siljit(this.tana, 'x', ishStolida ? 0.1 : 0.02);
      // Chanoq AYNAN o'tirgich ustida bo'lsin. Ilgari bu yerda qotirilgan
      // `-0.17` turardi — u faqat o'sha paytdagi o'lchamga (1.35) mos
      // kelardi, o'lcham o'zgarishi bilan agent stuldan yuqorida osilib
      // qolardi. Endi joriy o'lchamdan hisoblanadi, shuning uchun
      // tanlanib yiriklashganda ham joyida o'tiradi.
      this.guruh.position.y = STUL_USTI - this.chanoq * this.guruh.scale.y;
    } else {
      // Tik turibdi — hamma bo'g'im bo'shashadi.
      [...this.oyoqlar, ...this.qollar].forEach((b) => {
        b.rotation.x *= 0.85;
        const bola = b.userData.tizza || b.userData.tirsak;
        if (bola) bola.rotation.x *= 0.85;
      });
      this.qollar.forEach((q, i) => { q.rotation.z = (i === 0 ? 1 : -1) * 0.07; });
      this.tana.rotation.x *= 0.85;
      this.guruh.position.y = 0;
    }

    this.nuqta.material.color.set(a.holatRangi());
    const kutmoqda = a.holat === 'tasdiq_kutilmoqda';
    this.nuqta.scale.setScalar(
      kutmoqda ? 1 + Math.sin(performance.now() / 260) * 0.28 : 1,
    );
  }

  tanlanganini_belgila(tanlanganmi) {
    this.yorliq.material.opacity = tanlanganmi ? 1 : 0.9;
    this.guruh.scale.setScalar(tanlanganmi ? FIGURA_TANLANGAN : FIGURA_OLCHAMI);
  }
}

// --- sahna -------------------------------------------------------------------

export class Ofis3D {
  constructor(idish) {
    this.idish = idish;
    this.agentlar = new Map();
    this.agent3d = new Map();
    this.tanlangan = null;
    this._oxirgiTopshirish = null;
    this.oxirgiVaqt = performance.now();

    this.sahna = new THREE.Scene();
    this.sahna.background = new THREE.Color(RANG.fon);
    // Tuman UZOQROQ boshlanadi: oldin 40 birlikda boshlanib, ofisning
    // yarmini yuvib tashlardi va sahna xira ko'rinardi.
    this.sahna.fog = new THREE.Fog(RANG.fon, 75, 165);

    this.kamera = new THREE.PerspectiveCamera(46, 1, 0.1, 300);
    this.chizuvchi = new THREE.WebGLRenderer({ antialias: true });
    this.chizuvchi.shadowMap.enabled = true;
    this.chizuvchi.shadowMap.type = THREE.PCFSoftShadowMap;
    // Fotografik ton egri chizig'i: yorug' joylar kuyib ketmaydi, soyalar
    // ko'kimtir qoladi. Busiz `MeshStandardMaterial` "plastmassa" ko'rinadi.
    this.chizuvchi.toneMapping = THREE.ACESFilmicToneMapping;
    // Ekspozitsiya 1.0 — yorug'lik endi chiroqlarning O'ZIDAN keladi
    // (quyosh 3.1). Ekspozitsiyani ko'tarish esa hamma narsani, soya
    // bilan birga, bir xil ko'taradi va aynan kontrastni yo'qotadi.
    this.chizuvchi.toneMappingExposure = 1.0;
    this.chizuvchi.outputColorSpace = THREE.SRGBColorSpace;
    idish.appendChild(this.chizuvchi.domElement);

    // Kamera orbitasi (tashqi kutubxonasiz — kerakli minimum).
    //
    // Balandlik 0.78 -> 0.60, masofa 47 -> 36: oldin kamera deyarli
    // tepadan qarardi va ofis PLAN (chizma) bo'lib ko'rinardi. Pastroq
    // va yaqinroq burchakda devorlar yon tomondan ko'rinadi, odamlar
    // esa nuqta emas — figura bo'ladi.
    this.orbit = { burchak: -Math.PI / 2.6, balandlik: 0.64, masofa: 47 };
    this.markaz = new THREE.Vector3(XARITA_ENI / 2, 0, XARITA_BOYI / 2);

    this._yoritish();
    this._ofisniQur();
    this._hodisalar();
    this._olchamniMoslash();
    requestAnimationFrame(() => this._tsikl());
  }

  // --- qurilish --------------------------------------------------------------

  _yoritish() {
    // NISBAT — bu yerdagi eng muhim narsa.
    //
    // Avvalgi urinishda hamma qatlam ko'tarilgan edi (hemisphere 1.05 +
    // ambient 0.22 + to'ldiruvchi 0.55 + kontur 0.7 = 2.5, quyosh esa
    // atigi 1.45). To'ldiruvchi asosiydan kuchli bo'lgach soya yo'qoladi
    // va sahna "yassi rangli qog'oz" bo'lib qoladi — ekranda aynan
    // shunday chiqdi.
    //
    // Multfilm renderining qoidasi teskari: ASOSIY yorug'lik hukmron
    // (soya beradi, shakl ko'rsatadi), to'ldiruvchi esa PAST va RANGLI
    // bo'ladi — u soyani ochadi, lekin yo'qotmaydi. Shuning uchun
    // hozirgi nisbat ~ 3.1 : 1.
    //
    //   osmon        — yumshoq umumiy (ko'k tepadan, iliq pastdan)
    //   quyosh       — asosiy, soya beruvchi
    //   to'ldiruvchi — soyani ko'kimtir qiladi, qora qoldirmaydi
    //   kontur       — orqadan; shakl chetini yoritib fondan ajratadi
    this.sahna.add(new THREE.HemisphereLight(0xcfe4f7, 0xc28f60, 0.5));

    const quyosh = new THREE.DirectionalLight(0xfff1d2, 3.1);
    // Past burchak (52 -> 34): soyalar UZUNROQ tushadi. Tik quyosh
    // soyani predmet ostiga bosib qo'yadi va hajm ko'rinmaydi.
    quyosh.position.set(XARITA_ENI * 0.85, 34, XARITA_BOYI * 0.05);
    quyosh.castShadow = true;
    quyosh.shadow.mapSize.set(2048, 2048);
    // Soya "chiziqlari" (acne) va yuzadan uzilishiga qarshi.
    quyosh.shadow.bias = -0.0004;
    quyosh.shadow.normalBias = 0.02;
    quyosh.shadow.radius = 2.6;
    const k = quyosh.shadow.camera;
    k.left = -42; k.right = 42; k.top = 42; k.bottom = -42; k.far = 130;
    this.sahna.add(quyosh);

    const toldiruvchi = new THREE.DirectionalLight(0x9ec2e6, 0.42);
    toldiruvchi.position.set(-XARITA_ENI * 0.4, 22, XARITA_BOYI * 1.1);
    this.sahna.add(toldiruvchi);

    const kontur = new THREE.DirectionalLight(0xffd2a0, 0.55);
    kontur.position.set(-XARITA_ENI * 0.2, 10, -XARITA_BOYI * 0.5);
    this.sahna.add(kontur);
  }

  _ofisniQur() {
    const dunyo = new THREE.Group();

    // 1) Pol — har bo'lim o'z rangida, yo'laklar alohida.
    //    Har katak uchun alohida mesh qurish 1000+ chizish chaqiruvi berardi;
    //    rang bo'yicha guruhlab InstancedMesh ishlatamiz — bir necha chaqiruv.
    const polKataklari = new Map();   // rang -> [[x, y], ...]
    for (let y = 0; y < XARITA_BOYI; y++) {
      for (let x = 0; x < XARITA_ENI; x++) {
        if (XARITA[y][x] === DEVOR) continue;
        const bolim = bolimTop(x, y);
        const tus = String(
          yuribBoladi(x, y) && !bolim ? RANG.yolak : (bolim ? bolim.rang : RANG.yolak),
        );
        if (!polKataklari.has(tus)) polKataklari.set(tus, []);
        polKataklari.get(tus).push([x, y]);
      }
    }

    const polGeo = new THREE.BoxGeometry(1, 0.08, 1);
    const joylash = new THREE.Matrix4();
    const yolakTusi = String(RANG.yolak);
    polKataklari.forEach((kataklar, tus) => {
      // Yo'lakda parket, xonalarda gilam — material farqi ko'zga tashlanadi.
      const tekstura = tus === yolakTusi
        ? parketTeksturasi(css(tus)) : gilamTeksturasi(css(tus));
      const mesh = new THREE.InstancedMesh(
        polGeo,
        new THREE.MeshStandardMaterial({
          map: tekstura,
          roughness: tus === yolakTusi ? 0.55 : 0.95,
          metalness: 0,
        }),
        kataklar.length,
      );
      mesh.receiveShadow = true;
      kataklar.forEach(([x, y], i) => {
        joylash.setPosition(x + 0.5, -0.04, y + 0.5);
        mesh.setMatrixAt(i, joylash);
      });
      dunyo.add(mesh);
    });

    // 2) Devorlar — faqat yurish mumkin bo'lgan katakka tegib turganlari.
    //    Ichkarida ko'rinmaydigan bloklarni qurish bekorga yuk bo'lardi.
    const devorGeo = new THREE.BoxGeometry(1, DEVOR_BALANDLIGI, 1);
    // Tekstura NEYTRAL (oq) — asl rang endi har instansiyaga alohida
    // beriladi va shu oq naqshga ko'paytiriladi. Shunda bitta chizish
    // chaqirig'ida turli rangli devorlar chiqadi.
    const devorMat = new THREE.MeshStandardMaterial({
      map: devorTeksturasi('#ffffff'), roughness: 0.92, metalness: 0,
    });
    const devorlar = [];
    for (let y = 0; y < XARITA_BOYI; y++) {
      for (let x = 0; x < XARITA_ENI; x++) {
        if (XARITA[y][x] !== DEVOR) continue;
        const qoshni = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(
          ([dx, dy]) => XARITA[y + dy]?.[x + dx] !== undefined
            && XARITA[y + dy][x + dx] !== DEVOR,
        );
        if (qoshni) devorlar.push([x, y]);
      }
    }

    // DEVOR RANGI bo'limga ergashadi.
    //
    // Ilgari hamma devor bir xil krem edi — ofis bir bo'lak karton
    // bo'lib ko'rinardi. Endi har devor o'ziga tegib turgan xonaning
    // tusiga bir oz og'adi: xona chegarasi rangdan bilinadi, sahna esa
    // yaxlitligicha qoladi (og'ish 34%, undan ortig'i chalg'itadi).
    const asosTus = new THREE.Color(RANG.devor);
    const devorTusi = ([x, y], ogish = 0.34) => {
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const b = bolimTop(x + dx, y + dy);
        if (b) return asosTus.clone().lerp(new THREE.Color(b.rang), ogish);
      }
      return asosTus.clone();
    };

    const devorMesh = new THREE.InstancedMesh(devorGeo, devorMat, devorlar.length);
    devorMesh.castShadow = true;
    devorMesh.receiveShadow = true;
    devorlar.forEach(([x, y], i) => {
      joylash.setPosition(x + 0.5, DEVOR_BALANDLIGI / 2, y + 0.5);
      devorMesh.setMatrixAt(i, joylash);
      devorMesh.setColorAt(i, devorTusi([x, y]));
    });
    if (devorMesh.instanceColor) devorMesh.instanceColor.needsUpdate = true;
    dunyo.add(devorMesh);

    // 2b) Plintus va tepa karniz — devorni poldan va havodan ajratadi.
    //     Shu ikki chiziq ichki makonni "qurilgan" qilib ko'rsatadi.
    //
    //     KARNIZ tepadan qaraganda eng katta yuza — u devordan
    //     kengroq (1.07) va butun devor ustini qoplaydi. Ilgari u
    //     qo'ng'ir (0xbfae94) edi va ofisning YARMIDAN ko'pi shu
    //     jigarrang bilan qoplanib, sahna to'q va og'ir ko'rinardi.
    //     Endi u ham xona tusini oladi: har xona tepadan o'z rangi
    //     bilan CHIZILGAN bo'lib turadi — illyustratsiyadagi kontur
    //     chizig'i kabi.
    const plintusGeo = new THREE.BoxGeometry(1.04, 0.11, 1.04);
    const karnizGeo = new THREE.BoxGeometry(1.07, 0.07, 1.07);
    const oqMat = () => new THREE.MeshStandardMaterial({
      color: 0xffffff, roughness: 0.7, metalness: 0,
    });
    [[plintusGeo, 0.055, 0.86, 0.26], [karnizGeo, DEVOR_BALANDLIGI - 0.03, 1.06, 0.5]]
      .forEach(([geo, balandlik, yorqinlik, ogish]) => {
        const m = new THREE.InstancedMesh(geo, oqMat(), devorlar.length);
        m.receiveShadow = true;
        devorlar.forEach(([x, y], i) => {
          joylash.setPosition(x + 0.5, balandlik, y + 0.5);
          m.setMatrixAt(i, joylash);
          m.setColorAt(i, devorTusi([x, y], ogish).multiplyScalar(yorqinlik));
        });
        if (m.instanceColor) m.instanceColor.needsUpdate = true;
        dunyo.add(m);
      });

    // 3) Jihoz — bir xil turdagilar ham instansiyalanadi.
    const jihoz = { [MAJLIS]: [], [OSHXONA]: [], [SHKAF]: [] };
    for (let y = 0; y < XARITA_BOYI; y++) {
      for (let x = 0; x < XARITA_ENI; x++) {
        const katak = XARITA[y][x];
        if (katak === STOL) dunyo.add(this._stol(x, y));
        else if (katak === OSIMLIK) dunyo.add(this._osimlik(x, y));
        else if (jihoz[katak]) jihoz[katak].push([x, y]);
      }
    }
    // Majlis stoli va oshxona javoni — katak-katak quti emas, YAXLIT
    // jihoz. 26 ta kubdan yasalgan "plita" stolga o'xshamaydi.
    if (jihoz[MAJLIS].length) dunyo.add(this._majlisStoli(jihoz[MAJLIS]));
    if (jihoz[OSHXONA].length) dunyo.add(this._oshxona(jihoz[OSHXONA]));

    // Shkaflar — instansiya, lekin tepasida karniz bilan.
    if (jihoz[SHKAF].length) {
      const kataklar = jihoz[SHKAF];
      const shkafMat = new THREE.MeshStandardMaterial({
        map: yogochTeksturasi(css(RANG.shkaf)), roughness: 0.55, metalness: 0.03,
      });
      const korpus = new THREE.InstancedMesh(
        yumaloqQuti(0.94, 1.22, 0.94, 0.06, 0.022), shkafMat, kataklar.length,
      );
      korpus.castShadow = true;
      korpus.receiveShadow = true;
      const qopqoq = new THREE.InstancedMesh(
        new THREE.BoxGeometry(1, 0.05, 1),
        new THREE.MeshStandardMaterial({ color: 0x6f4b28, roughness: 0.5 }),
        kataklar.length,
      );
      kataklar.forEach(([x, y], i) => {
        joylash.setPosition(x + 0.5, 0.61, y + 0.5);
        korpus.setMatrixAt(i, joylash);
        joylash.setPosition(x + 0.5, 1.25, y + 0.5);
        qopqoq.setMatrixAt(i, joylash);
      });
      dunyo.add(korpus, qopqoq);
    }

    // 3b) Majlis stoli atrofidagi 12 ta stul — savol chiqqanda jamoa
    //     shu yerga kelib O'TIRADI, tik turmaydi.
    MAJLIS_JOYLARI.forEach(([x, y]) => {
      // Stol y:33..34 da. Yuqoridagi qator stolga qarab (suyanchiq orqada),
      // pastdagi qator teskari buriladi.
      const burilish = y < 33 ? Math.PI : 0;
      dunyo.add(this._stul(x + 0.5, y + 0.5, burilish));
    });

    // 3c) Oshxona: ovqatlanish stollari va ular atrofidagi 4 tadan stul.
    OSH_STOLLARI.forEach(([x, y]) => {
      dunyo.add(this._ovqatStoli(x, y));
      [[-1, 0, -Math.PI / 2], [1, 0, Math.PI / 2], [0, -1, Math.PI], [0, 1, 0]]
        .forEach(([dx, dy, burilish]) => {
          dunyo.add(this._stul(x + 0.5 + dx, y + 0.5 + dy, burilish));
        });
    });

    // 3d) Xona bezaklari: divan, jurnal stolchasi, javon, muzlatgich —
    //     polda; doska va ramkalar — devorda.
    BEZAKLAR.forEach((b) => {
      const jismi = this._bezak(b);
      if (jismi) dunyo.add(jismi);
    });
    DEVOR_BEZAKLARI.forEach((b) => {
      const jismi = this._devorBezagi(b);
      if (jismi) dunyo.add(jismi);
    });

    // 4) Bo'lim yorliqlari — havoda turadi
    BOLIMLAR.forEach((b) => {
      const yorliq = yorliqYasa(b.nom, '#ffe9c9', 40, 58, 'xona');
      yorliq.position.set(b.x + b.w / 2, 4.2, b.y + b.h / 2);
      dunyo.add(yorliq);
    });

    this.sahna.add(dunyo);
  }

  // Kataklar to'plamining chegarasi — yaxlit jihoz o'lchamini beradi.
  static _quti(kataklar) {
    const xs = kataklar.map((k) => k[0]);
    const ys = kataklar.map((k) => k[1]);
    const x0 = Math.min(...xs);
    const y0 = Math.min(...ys);
    return {
      x0, y0, en: Math.max(...xs) - x0 + 1, boy: Math.max(...ys) - y0 + 1,
      markazX: x0 + (Math.max(...xs) - x0 + 1) / 2,
      markazZ: y0 + (Math.max(...ys) - y0 + 1) / 2,
    };
  }

  // Majlis stoli: bitta uzun usti + ikki tomonda tayanch oyoqlar.
  _majlisStoli(kataklar) {
    const q = Ofis3D._quti(kataklar);
    const guruh = new THREE.Group();
    const balandlik = MAJLIS_BALANDLIGI;
    const yogoch = new THREE.MeshStandardMaterial({
      map: yogochTeksturasi(css(RANG.majlis)), roughness: 0.35, metalness: 0.04,
    });
    const metall = new THREE.MeshStandardMaterial({
      color: 0x7e848c, roughness: 0.35, metalness: 0.8,
    });

    const ust = new THREE.Mesh(
      yumaloqQuti(q.en - 0.2, 0.07, q.boy - 0.15, 0.22, 0.02), yogoch,
    );
    ust.position.set(q.markazX, balandlik, q.markazZ);
    ust.castShadow = true;
    ust.receiveShadow = true;
    guruh.add(ust);

    // Ikki uchida "T" shaklidagi tayanch — konferens stoliga xos.
    [-1, 1].forEach((tomon) => {
      const x = q.markazX + tomon * (q.en / 2 - 1.4);
      const ustun = new THREE.Mesh(new THREE.BoxGeometry(0.14, balandlik - 0.07, 0.5), metall);
      ustun.position.set(x, (balandlik - 0.07) / 2, q.markazZ);
      ustun.castShadow = true;
      const oyoq = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.06, q.boy - 0.4), metall);
      oyoq.position.set(x, 0.03, q.markazZ);
      guruh.add(ustun, oyoq);
    });

    // Stol ustida bir nechta hujjat va stakan — bo'sh stol sovuq ko'rinadi.
    const qogoz = new THREE.MeshStandardMaterial({ color: 0xf3efe6, roughness: 0.95 });
    const shisha = new THREE.MeshStandardMaterial({
      color: 0xbcd8e0, roughness: 0.1, metalness: 0.1,
      transparent: true, opacity: 0.55,
    });
    for (let i = 0; i < 6; i++) {
      const x = q.x0 + 1.5 + i * ((q.en - 3) / 5);
      const varaq = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.006, 0.22), qogoz);
      varaq.position.set(x, balandlik + 0.038, q.markazZ + (i % 2 ? 0.4 : -0.4));
      varaq.rotation.y = (Math.random() - 0.5) * 0.4;
      guruh.add(varaq);
    }
    for (let i = 0; i < 3; i++) {
      const stakan = new THREE.Mesh(
        new THREE.CylinderGeometry(0.045, 0.038, 0.11, 12), shisha,
      );
      stakan.position.set(q.x0 + 2.5 + i * ((q.en - 5) / 2), balandlik + 0.09, q.markazZ);
      guruh.add(stakan);
    }
    return guruh;
  }

  // Oshxona: pastki javon + ustki shkaf + rakovina.
  _oshxona(kataklar) {
    const q = Ofis3D._quti(kataklar);
    const guruh = new THREE.Group();
    const yogoch = new THREE.MeshStandardMaterial({
      map: yogochTeksturasi(css(RANG.oshxona)), roughness: 0.6, metalness: 0.02,
    });
    const tosh = new THREE.MeshStandardMaterial({
      color: 0x4d5158, roughness: 0.28, metalness: 0.12,
    });
    const metall = new THREE.MeshStandardMaterial({
      color: 0xb9bfc6, roughness: 0.25, metalness: 0.85,
    });

    const javon = new THREE.Mesh(yumaloqQuti(q.en - 0.1, 0.72, 0.8, 0.07, 0.022), yogoch);
    javon.position.set(q.markazX, 0.36, q.markazZ);
    javon.castShadow = true;
    javon.receiveShadow = true;
    guruh.add(javon);

    const stolust = new THREE.Mesh(yumaloqQuti(q.en, 0.06, 0.88, 0.07, 0.018), tosh);
    stolust.position.set(q.markazX, 0.75, q.markazZ);
    stolust.castShadow = true;
    guruh.add(stolust);

    // Rakovina va jo'mrak
    const chuqurcha = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.05, 0.5), metall);
    chuqurcha.position.set(q.markazX - 1.6, 0.76, q.markazZ);
    guruh.add(chuqurcha);
    const jomrak = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.3, 8), metall);
    jomrak.position.set(q.markazX - 1.6, 0.92, q.markazZ - 0.25);
    guruh.add(jomrak);

    // Ustki shkaflar — devorga osilgan
    const ustki = new THREE.Mesh(yumaloqQuti(q.en - 1.2, 0.62, 0.42, 0.06, 0.02), yogoch);
    ustki.position.set(q.markazX, 1.45, q.markazZ - 0.3);
    ustki.castShadow = true;
    guruh.add(ustki);

    // Qahva mashinasi
    const qahva = new THREE.Mesh(yumaloqQuti(0.34, 0.42, 0.3, 0.05, 0.018),
      new THREE.MeshStandardMaterial({ color: 0x2b2d31, roughness: 0.4, metalness: 0.2 }));
    qahva.position.set(q.markazX + 1.9, 0.99, q.markazZ);
    qahva.castShadow = true;
    guruh.add(qahva);

    return guruh;
  }

  // Oshxonadagi dumaloq ovqatlanish stoli — bir oyoqli, ustida likopcha.
  _ovqatStoli(x, y) {
    const guruh = new THREE.Group();
    const balandlik = MAJLIS_BALANDLIGI;
    const ustMat = new THREE.MeshStandardMaterial({
      map: yogochTeksturasi(css(RANG.stolUst)), roughness: 0.4, metalness: 0.03,
    });
    const metall = new THREE.MeshStandardMaterial({
      color: 0x8f959c, roughness: 0.3, metalness: 0.8,
    });

    const ust = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.46, 0.05, 24), ustMat);
    ust.position.y = balandlik;
    ust.castShadow = true;
    ust.receiveShadow = true;
    guruh.add(ust);

    const ustun = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, 0.06, balandlik - 0.05, 12), metall,
    );
    ustun.position.y = (balandlik - 0.05) / 2;
    ustun.castShadow = true;
    guruh.add(ustun);

    const tayanch = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.26, 0.035, 20), metall);
    tayanch.position.y = 0.018;
    guruh.add(tayanch);

    // Ustida bir nechta likopcha va stakan
    const oq = new THREE.MeshStandardMaterial({ color: 0xf0ece3, roughness: 0.35 });
    [[0.18, 0.12], [-0.2, -0.08], [0.02, -0.22]].forEach(([dx, dz], i) => {
      const likopcha = new THREE.Mesh(
        new THREE.CylinderGeometry(0.1, 0.085, 0.018, 16), oq,
      );
      likopcha.position.set(dx, balandlik + 0.035, dz);
      guruh.add(likopcha);
      if (i === 0) {
        const stakan = new THREE.Mesh(
          new THREE.CylinderGeometry(0.04, 0.034, 0.1, 12),
          new THREE.MeshStandardMaterial({
            color: 0xbcd8e0, roughness: 0.12, transparent: true, opacity: 0.6,
          }),
        );
        stakan.position.set(dx - 0.22, balandlik + 0.075, dz - 0.1);
        guruh.add(stakan);
      }
    });

    guruh.position.set(x + 0.5, 0, y + 0.5);
    return guruh;
  }

  // Ish joyi: stol (yupqa usti + metall oyoqlar), monitor oyoqchada,
  // klaviatura, sichqoncha va aylanuvchi stul. Bitta quti o'rniga
  // shular — ofis birdan tanish ko'rinadi.
  _stol(x, y) {
    const guruh = new THREE.Group();
    const yogoch = new THREE.MeshStandardMaterial({
      map: yogochTeksturasi(css(RANG.stolUst)), roughness: 0.5, metalness: 0.02,
    });
    const metall = new THREE.MeshStandardMaterial({
      color: 0x9aa0a6, roughness: 0.35, metalness: 0.75,
    });
    const plastik = new THREE.MeshStandardMaterial({
      color: 0x2c2e33, roughness: 0.55, metalness: 0.1,
    });

    const ust = new THREE.Mesh(yumaloqQuti(0.96, 0.045, 0.74, 0.05, 0.014), yogoch);
    ust.position.y = STOL_BALANDLIGI;
    ust.castShadow = true;
    ust.receiveShadow = true;
    guruh.add(ust);

    // To'rt oyoq — soya ostida bo'shliq paydo bo'ladi, "quti" bo'lib qolmaydi.
    [[-0.42, -0.3], [0.42, -0.3], [-0.42, 0.3], [0.42, 0.3]].forEach(([ox, oz]) => {
      const oyoq = new THREE.Mesh(
        new THREE.CylinderGeometry(0.022, 0.022, STOL_BALANDLIGI, 8), metall,
      );
      oyoq.position.set(ox, STOL_BALANDLIGI / 2, oz);
      oyoq.castShadow = true;
      guruh.add(oyoq);
    });
    // Oyoqlar orasidagi bog'lovchi
    const bogich = new THREE.Mesh(new THREE.BoxGeometry(0.86, 0.02, 0.03), metall);
    bogich.position.set(0, 0.12, -0.3);
    guruh.add(bogich);

    // Monitor: oyoqcha + tayanch + ekran (yorug' tomoni oldinga)
    const tayanch = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.12, 0.014, 14), plastik);
    tayanch.position.set(0, STOL_BALANDLIGI + 0.03, -0.2);
    guruh.add(tayanch);
    const ustun = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.16, 0.03), plastik);
    ustun.position.set(0, STOL_BALANDLIGI + 0.11, -0.2);
    guruh.add(ustun);

    const korpus = new THREE.Mesh(yumaloqQuti(0.56, 0.34, 0.022, 0.022, 0.007), plastik);
    korpus.position.set(0, STOL_BALANDLIGI + 0.3, -0.2);
    korpus.rotation.x = -0.09;
    korpus.castShadow = true;
    guruh.add(korpus);
    const ekran = new THREE.Mesh(
      new THREE.PlaneGeometry(0.51, 0.29),
      new THREE.MeshStandardMaterial({
        color: 0x1a2430, emissive: RANG.monitorYoniq, emissiveIntensity: 0.55,
        roughness: 0.25,
      }),
    );
    ekran.position.set(0, STOL_BALANDLIGI + 0.3, -0.187);
    ekran.rotation.x = -0.09;
    guruh.add(ekran);

    const klaviatura = new THREE.Mesh(yumaloqQuti(0.42, 0.016, 0.15, 0.014, 0.005), plastik);
    klaviatura.position.set(-0.04, STOL_BALANDLIGI + 0.03, 0.12);
    guruh.add(klaviatura);
    const sichqoncha = new THREE.Mesh(new THREE.SphereGeometry(0.035, 10, 8), plastik);
    sichqoncha.scale.set(0.7, 0.4, 1);
    sichqoncha.position.set(0.28, STOL_BALANDLIGI + 0.035, 0.12);
    guruh.add(sichqoncha);

    // Stul agent o'tiradigan katakning ayni markazida (stoldan 1 katak
    // pastda) va suyanchig'i stoldan NARIGA qaraydi.
    guruh.add(this._stul(0, 1.0, 0));
    guruh.position.set(x + 0.5, 0, y + 0.5);
    return guruh;
  }

  // Ofis stuli — o'tirgich, suyanchiq va besh oyoqli krestovina.
  // `burilish`: suyanchiq qaysi tomonda tursin (0 = +z tomonda, ya'ni
  // o'tirgan odam -z ga, ya'ni stolga qaraydi).
  _stul(x, z, burilish = 0) {
    const guruh = new THREE.Group();
    const mato = new THREE.MeshStandardMaterial({
      color: 0x3f4650, roughness: 0.9, metalness: 0,
    });
    const metall = new THREE.MeshStandardMaterial({
      color: 0x8d939a, roughness: 0.4, metalness: 0.7,
    });

    const otirgich = new THREE.Mesh(yumaloqQuti(0.44, 0.07, 0.42, 0.09, 0.022), mato);
    otirgich.position.y = STUL_USTI - 0.035;
    otirgich.castShadow = true;
    guruh.add(otirgich);

    const suyanchiq = new THREE.Mesh(yumaloqQuti(0.42, 0.42, 0.06, 0.085, 0.02), mato);
    suyanchiq.position.set(0, STUL_USTI + 0.21, 0.19);
    suyanchiq.rotation.x = 0.13;
    suyanchiq.castShadow = true;
    guruh.add(suyanchiq);

    const ustunBoyi = STUL_USTI - 0.115;
    const ustun = new THREE.Mesh(
      new THREE.CylinderGeometry(0.03, 0.035, ustunBoyi, 10), metall,
    );
    ustun.position.y = 0.045 + ustunBoyi / 2;
    guruh.add(ustun);

    for (let i = 0; i < 5; i++) {
      const burchak = (i / 5) * Math.PI * 2;
      const oyoq = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.025, 0.045), metall);
      oyoq.position.set(Math.cos(burchak) * 0.12, 0.045, Math.sin(burchak) * 0.12);
      oyoq.rotation.y = -burchak;
      guruh.add(oyoq);
    }

    guruh.position.set(x, 0, z);
    guruh.rotation.y = burilish;
    return guruh;
  }

  // --- xona bezaklari --------------------------------------------------------
  //
  // Xonalar bo'm-bo'sh edi: to'rt devor, bir nechta stol va katta bo'sh
  // pol. Quyidagilar shu bo'shliqni to'ldiradi. Geometriya shu yerda,
  // JOYLASHUV esa `ofis-model.js` da — bitta manba, chunki polda turgan
  // bezak katakni egallaydi va yo'l topishga ta'sir qiladi.

  // Model HAR DOIM +z ga qarab quriladi, so'ng `buril` bilan buriladi.
  // Xaritadagi `en`/`boy` o'q bo'ylab o'lchov — 90° burilganda ular
  // o'rin almashadi, shuning uchun modelga alohida hisoblab beriladi.
  static _olcham({ en, boy, buril = 0 }) {
    const yonlama = Math.abs(Math.sin(buril)) > 0.5;
    return { en: yonlama ? boy : en, chuq: yonlama ? en : boy };
  }

  _bezak(bezak) {
    const yasovchi = {
      divan: (b, o) => this._divan(b, o),
      stolcha: (b, o) => this._stolcha(b, o),
      javon: (b, o) => this._javon(b, o),
      muzlatgich: (b, o) => this._muzlatgich(b, o),
    }[bezak.tur];
    if (!yasovchi) return null;

    const guruh = yasovchi(bezak, Ofis3D._olcham(bezak));
    guruh.position.set(bezak.x + bezak.en / 2, 0, bezak.y + bezak.boy / 2);
    guruh.rotation.y = bezak.buril || 0;
    return guruh;
  }

  // Divan: o'tirgich, suyanchiq, ikki yonbosh va yostiqlar. Balandligi
  // stul bilan bir xil (STUL_USTI) — bir xonada turganda bo'y farqi
  // ko'zga tashlanmasin.
  _divan(bezak, { en, chuq }) {
    const guruh = new THREE.Group();
    const mato = new THREE.MeshStandardMaterial({
      color: RANG.divan, roughness: 0.95, metalness: 0,
    });
    const yostiqMat = new THREE.MeshStandardMaterial({
      color: RANG.divanYostiq, roughness: 0.9, metalness: 0,
    });
    const oyoqMat = new THREE.MeshStandardMaterial({
      color: 0x4a3a2a, roughness: 0.5, metalness: 0.1,
    });

    // Uzunlik CHEKLANADI. Katak soniga to'liq cho'zilsa (3 katak = 2.8)
    // divan emas, uzun skameyka chiqadi — birinchi urinishda aynan
    // shunday bo'ldi. Bo'yi ~1.95 bo'lgan odam uchun 2.3 dan uzun
    // o'rindiq g'ayritabiiy ko'rinadi.
    const uzunlik = Math.min(en - 0.2, 2.3);
    const chuqurlik = Math.min(chuq - 0.12, 0.92);
    const otirgichY = STUL_USTI - 0.05;

    const tag = new THREE.Mesh(
      yumaloqQuti(uzunlik, 0.18, chuqurlik, 0.1, 0.03), mato,
    );
    tag.position.y = otirgichY;
    tag.castShadow = true;
    tag.receiveShadow = true;
    guruh.add(tag);

    // Suyanchiq orqada (-z), chunki model +z ga qaraydi. Qalin va
    // baland: ingichka suyanchiq divanni skameykaga o'xshatib qo'yadi.
    const suyanchiq = new THREE.Mesh(
      yumaloqQuti(uzunlik, 0.52, 0.22, 0.09, 0.035), mato,
    );
    suyanchiq.position.set(0, otirgichY + 0.3, -chuqurlik / 2 + 0.11);
    suyanchiq.castShadow = true;
    guruh.add(suyanchiq);

    [-1, 1].forEach((tomon) => {
      const yonbosh = new THREE.Mesh(
        yumaloqQuti(0.2, 0.36, chuqurlik, 0.09, 0.035), mato,
      );
      yonbosh.position.set(tomon * (uzunlik / 2 - 0.1), otirgichY + 0.18, 0);
      yonbosh.castShadow = true;
      guruh.add(yonbosh);
    });

    // O'tirgich yostiqlari — bir xil matoda, faqat oralarida chok
    // ko'rinib tursin. Rangni almashtirish "shaxmat taxta" effektini
    // beradi va arzon ko'rinadi.
    const ichkiEn = uzunlik - 0.44;
    const soni = ichkiEn > 1.5 ? 3 : 2;
    const yostiqEni = ichkiEn / soni;
    const yorqinMato = new THREE.MeshStandardMaterial({
      color: new THREE.Color(RANG.divan).offsetHSL(0, 0.02, 0.06),
      roughness: 0.95,
    });
    for (let i = 0; i < soni; i++) {
      const yostiq = new THREE.Mesh(
        yumaloqQuti(yostiqEni - 0.05, 0.14, chuqurlik - 0.28, 0.07, 0.035),
        yorqinMato,
      );
      yostiq.position.set(
        -ichkiEn / 2 + yostiqEni * (i + 0.5), otirgichY + 0.14, 0.05,
      );
      yostiq.castShadow = true;
      guruh.add(yostiq);
    }

    // Bezak yostiqchalari — divandagi yagona iliq dog'. Multfilm
    // interyerida aynan shu mayda aksent xonani "yashatadi".
    [-1, 1].forEach((tomon) => {
      const yostiqcha = new THREE.Mesh(
        yumaloqQuti(0.26, 0.26, 0.1, 0.06, 0.035), yostiqMat,
      );
      yostiqcha.position.set(
        tomon * (uzunlik / 2 - 0.32), otirgichY + 0.3, -chuqurlik / 2 + 0.28,
      );
      yostiqcha.rotation.set(0.34, 0, tomon * 0.16);
      yostiqcha.castShadow = true;
      guruh.add(yostiqcha);
    });

    // Oyoqlar — divan poldan uziladi va ostida soya paydo bo'ladi.
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz]) => {
      const boyi = otirgichY - 0.08;
      const oyoq = new THREE.Mesh(
        new THREE.CylinderGeometry(0.035, 0.03, boyi, 8), oyoqMat,
      );
      oyoq.position.set(
        sx * (uzunlik / 2 - 0.12), boyi / 2, sz * (chuqurlik / 2 - 0.12),
      );
      oyoq.castShadow = true;
      guruh.add(oyoq);
    });

    return guruh;
  }

  // Jurnal stolchasi — divan oldida, ustida bir-ikki jurnal.
  _stolcha(bezak, { en, chuq }) {
    const guruh = new THREE.Group();
    const ustMat = new THREE.MeshStandardMaterial({
      map: yogochTeksturasi(css(RANG.stolUst)), roughness: 0.45, metalness: 0.03,
    });
    const oyoqMat = new THREE.MeshStandardMaterial({
      color: 0x6b4a2c, roughness: 0.55, metalness: 0.05,
    });

    const eni = en - 0.28;
    const chuqurligi = chuq - 0.28;
    const balandlik = 0.3;

    const ust = new THREE.Mesh(
      yumaloqQuti(eni, 0.05, chuqurligi, 0.08, 0.016), ustMat,
    );
    ust.position.y = balandlik;
    ust.castShadow = true;
    ust.receiveShadow = true;
    guruh.add(ust);

    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz]) => {
      const oyoq = new THREE.Mesh(
        new THREE.CylinderGeometry(0.026, 0.022, balandlik, 8), oyoqMat,
      );
      oyoq.position.set(
        sx * (eni / 2 - 0.08), balandlik / 2, sz * (chuqurligi / 2 - 0.08),
      );
      oyoq.castShadow = true;
      guruh.add(oyoq);
    });

    // Ustida jurnallar — bo'sh stol tugallanmagan ko'rinadi.
    ['#d9694f', '#e8dccb'].forEach((tus, i) => {
      const jurnal = new THREE.Mesh(
        yumaloqQuti(0.26, 0.014, 0.19, 0.015, 0.005),
        new THREE.MeshStandardMaterial({ color: tus, roughness: 0.85 }),
      );
      jurnal.position.set(-0.03 + i * 0.02, balandlik + 0.032 + i * 0.015, i * 0.03);
      jurnal.rotation.y = (i - 0.5) * 0.3;
      guruh.add(jurnal);
    });

    return guruh;
  }

  // Hujjat javoni — ochiq tokchali, rangli kitob bloklari bilan.
  _javon(bezak, { en, chuq }) {
    const guruh = new THREE.Group();
    const yogoch = new THREE.MeshStandardMaterial({
      map: yogochTeksturasi(css(RANG.shkaf)), roughness: 0.6, metalness: 0.02,
    });

    const eni = en - 0.18;
    const chuqurligi = Math.min(chuq - 0.2, 0.42);
    const balandlik = 1.5;

    // Korpus OCHIQ OLDLI bo'lishi shart. Birinchi urinishda u yaxlit
    // quti edi va tokchalar bilan kitoblar uning ICHIDA qolib ketdi —
    // devorga suyalgan yog'och taxta ko'rinardi, javon emas.
    const q = 0.05;   // panel qalinligi
    const panellar = [
      // orqa devor
      [yumaloqQuti(eni, balandlik, q, 0.03, 0.015), 0, balandlik / 2, -chuqurligi / 2 + q / 2],
      // yon devorlar
      [yumaloqQuti(q, balandlik, chuqurligi, 0.03, 0.015), -(eni / 2 - q / 2), balandlik / 2, 0],
      [yumaloqQuti(q, balandlik, chuqurligi, 0.03, 0.015), eni / 2 - q / 2, balandlik / 2, 0],
      // tepa va tag
      [yumaloqQuti(eni, q, chuqurligi, 0.03, 0.015), 0, balandlik - q / 2, 0],
      [yumaloqQuti(eni, q, chuqurligi, 0.03, 0.015), 0, q / 2, 0],
    ];
    panellar.forEach(([geo, px, py, pz]) => {
      const panel = new THREE.Mesh(geo, yogoch);
      panel.position.set(px, py, pz);
      panel.castShadow = true;
      panel.receiveShadow = true;
      guruh.add(panel);
    });

    // Kitob rangi va o'lchami TASODIFIY EMAS — o'rindan hisoblanadi,
    // shunda javon har yuklashda bir xil ko'rinadi.
    const kitobRangi = ['#b5503f', '#3f6f8f', '#c9a24a', '#5f7f4a', '#8a5f9e'];
    const tokchaSoni = 4;
    for (let t = 0; t < tokchaSoni; t++) {
      const y = 0.18 + t * ((balandlik - 0.3) / tokchaSoni);
      const tokcha = new THREE.Mesh(
        yumaloqQuti(eni - 2 * q, 0.03, chuqurligi - q, 0.02, 0.01), yogoch,
      );
      tokcha.position.set(0, y, q / 2);
      tokcha.receiveShadow = true;
      guruh.add(tokcha);

      let x = -eni / 2 + 0.08;
      let n = 0;
      while (x < eni / 2 - 0.12) {
        const qalinlik = 0.035 + ((t * 7 + n * 3) % 5) * 0.012;
        const boyi = 0.2 + ((t * 5 + n * 2) % 4) * 0.03;
        const kitob = new THREE.Mesh(
          new THREE.BoxGeometry(qalinlik, boyi, chuqurligi * 0.72),
          new THREE.MeshStandardMaterial({
            color: kitobRangi[(t * 3 + n) % kitobRangi.length], roughness: 0.9,
          }),
        );
        kitob.position.set(x + qalinlik / 2, y + 0.015 + boyi / 2, chuqurligi * 0.06);
        kitob.castShadow = true;
        guruh.add(kitob);
        x += qalinlik + 0.008;
        n += 1;
      }
    }

    return guruh;
  }

  // Oshxona muzlatgichi — ikki eshikli, dastalari bilan.
  _muzlatgich(bezak, { en, chuq }) {
    const guruh = new THREE.Group();
    const korpusMat = new THREE.MeshStandardMaterial({
      color: 0xd8dde2, roughness: 0.32, metalness: 0.55,
    });
    const dastaMat = new THREE.MeshStandardMaterial({
      color: 0x9aa2aa, roughness: 0.25, metalness: 0.85,
    });

    const eni = Math.min(en - 0.16, 0.86);
    const chuqurligi = Math.min(chuq - 0.16, 0.78);
    const balandlik = 1.62;

    const korpus = new THREE.Mesh(
      yumaloqQuti(eni, balandlik, chuqurligi, 0.06, 0.025), korpusMat,
    );
    korpus.position.y = balandlik / 2;
    korpus.castShadow = true;
    korpus.receiveShadow = true;
    guruh.add(korpus);

    const chok = new THREE.Mesh(
      new THREE.BoxGeometry(eni - 0.06, 0.012, 0.01),
      new THREE.MeshStandardMaterial({ color: 0x8f979e, roughness: 0.4 }),
    );
    chok.position.set(0, balandlik * 0.62, chuqurligi / 2 + 0.002);
    guruh.add(chok);

    [balandlik * 0.74, balandlik * 0.48].forEach((y) => {
      const dasta = new THREE.Mesh(
        new THREE.CylinderGeometry(0.018, 0.018, 0.26, 8), dastaMat,
      );
      dasta.position.set(eni * 0.3, y, chuqurligi / 2 + 0.035);
      dasta.castShadow = true;
      guruh.add(dasta);
    });

    return guruh;
  }

  // --- devorga osilganlar ----------------------------------------------------
  //
  // Bular pol katagini EGALLAMAYDI — devor yuzasiga yopishtiriladi,
  // shuning uchun yo'l topishga umuman ta'sir qilmaydi.
  _devorBezagi(bezak) {
    const guruh = bezak.tur === 'doska' ? this._doska(bezak) : this._ramka(bezak);
    if (!guruh) return null;
    const [dx, dy] = bezak.yon;
    guruh.position.set(bezak.x + 0.5 + dx * 0.505, 0, bezak.y + 0.5 + dy * 0.505);
    // Model +z ga qaragan — uni `yon` yo'nalishiga buramiz.
    guruh.rotation.y = Math.atan2(dx, dy);
    return guruh;
  }

  // Marker doskasi — ramka, yozuvli yuza va marker tokchasi.
  _doska(bezak) {
    const guruh = new THREE.Group();
    const eni = (bezak.en || 2) - 0.35;
    const balandlik = 1.05;
    const markaz = 1.32;

    const ramka = new THREE.Mesh(
      yumaloqQuti(eni + 0.08, balandlik + 0.08, 0.05, 0.02, 0.012),
      new THREE.MeshStandardMaterial({ color: 0xb9c0c6, roughness: 0.4, metalness: 0.5 }),
    );
    ramka.position.y = markaz;
    ramka.castShadow = true;
    guruh.add(ramka);

    const yuza = new THREE.Mesh(
      new THREE.PlaneGeometry(eni, balandlik),
      new THREE.MeshStandardMaterial({
        map: doskaTeksturasi(), roughness: 0.28, metalness: 0,
      }),
    );
    yuza.position.set(0, markaz, 0.028);
    guruh.add(yuza);

    const tokcha = new THREE.Mesh(
      yumaloqQuti(eni * 0.5, 0.035, 0.07, 0.015, 0.01),
      new THREE.MeshStandardMaterial({ color: 0xa9b0b6, roughness: 0.45, metalness: 0.4 }),
    );
    tokcha.position.set(0, markaz - balandlik / 2 - 0.05, 0.05);
    tokcha.castShadow = true;
    guruh.add(tokcha);

    ['#c0453a', '#2f6f9e'].forEach((tus, i) => {
      const marker = new THREE.Mesh(
        new THREE.CylinderGeometry(0.014, 0.014, 0.12, 8),
        new THREE.MeshStandardMaterial({ color: tus, roughness: 0.5 }),
      );
      marker.rotation.z = Math.PI / 2;
      marker.position.set(-0.1 + i * 0.16, markaz - balandlik / 2 - 0.02, 0.05);
      guruh.add(marker);
    });

    return guruh;
  }

  // Devordagi ramka — yog'och ramka + rangli surat.
  _ramka(bezak) {
    const guruh = new THREE.Group();
    const eni = 0.52;
    const balandlik = 0.66;
    const markaz = 1.42;

    const ramka = new THREE.Mesh(
      yumaloqQuti(eni, balandlik, 0.04, 0.015, 0.01),
      new THREE.MeshStandardMaterial({ color: RANG.ramkaYogoch, roughness: 0.55 }),
    );
    ramka.position.y = markaz;
    ramka.castShadow = true;
    guruh.add(ramka);

    const surat = new THREE.Mesh(
      new THREE.PlaneGeometry(eni - 0.09, balandlik - 0.09),
      new THREE.MeshStandardMaterial({
        map: suratTeksturasi(bezak.tus || '#3f7f9e'), roughness: 0.6,
      }),
    );
    surat.position.set(0, markaz, 0.023);
    guruh.add(surat);

    return guruh;
  }

  _osimlik(x, y) {
    const guruh = new THREE.Group();
    const tuvak = new THREE.Mesh(
      new THREE.CylinderGeometry(0.19, 0.14, 0.28, 16),
      new THREE.MeshStandardMaterial({ color: RANG.tuvak, roughness: 0.8 }),
    );
    tuvak.position.y = 0.14;
    tuvak.castShadow = true;
    tuvak.receiveShadow = true;
    guruh.add(tuvak);

    // Tuproq
    const tuproq = new THREE.Mesh(
      new THREE.CylinderGeometry(0.175, 0.175, 0.03, 16),
      new THREE.MeshStandardMaterial({ color: 0x3b2b1e, roughness: 1 }),
    );
    tuproq.position.y = 0.275;
    guruh.add(tuproq);

    // Poya + bir necha barg to'plami — bitta shar emas, o'simlikka o'xshaydi.
    const yashil = new THREE.MeshStandardMaterial({
      color: RANG.osimlik, roughness: 0.85, metalness: 0,
    });
    const poya = new THREE.Mesh(
      new THREE.CylinderGeometry(0.018, 0.026, 0.3, 6),
      new THREE.MeshStandardMaterial({ color: 0x4a6b3c, roughness: 0.9 }),
    );
    poya.position.y = 0.42;
    guruh.add(poya);

    const shokh = [
      [0, 0.72, 0, 0.22], [0.13, 0.62, 0.06, 0.15], [-0.12, 0.6, -0.07, 0.14],
      [0.05, 0.55, -0.13, 0.12], [-0.06, 0.68, 0.12, 0.13],
    ];
    shokh.forEach(([bx, by, bz, r]) => {
      const barg = new THREE.Mesh(new THREE.SphereGeometry(r, 10, 8), yashil);
      barg.scale.set(1, 0.75, 1);
      barg.position.set(bx, by, bz);
      barg.castShadow = true;
      guruh.add(barg);
    });

    guruh.position.set(x + 0.5, 0, y + 0.5);
    guruh.rotation.y = Math.random() * Math.PI;
    return guruh;
  }


  // --- boshqaruv -------------------------------------------------------------

  _hodisalar() {
    const el = this.chizuvchi.domElement;
    let suriladi = false;
    let suradi = false;      // Shift yoki o'rta tugma — kamerani ko'chirish
    let oxirgi = { x: 0, y: 0 };

    // --- ikki barmoq: zoom + ko'chirish ---
    //
    // Kanvasda `touch-action: none` turibdi (bir barmoq bilan sahnani
    // aylantirish uchun shart), lekin u brauzerning O'Z pinch-zoomini
    // ham o'chiradi. Shuning uchun ikki barmoqni o'zimiz sanaymiz.
    //
    // Kamerani KO'CHIRISH kompyuterda Shift yoki o'rta tugma bilan
    // qilinadi — telefonda ikkalasi ham yo'q. Shuning uchun ikki
    // barmoq bir vaqtda ikkita ish qiladi:
    //     barmoqlar orasi o'zgarsa   -> zoom
    //     barmoqlar birga surilsa    -> ko'chirish
    // Bu telefonlarda odatiy xarita ishorasi, o'rgatish shart emas.
    const barmoqlar = new Map();          // pointerId -> {x, y}
    let pinchMasofa = 0;                  // 0 = pinch rejimida emasmiz
    let pinchOrta = null;                 // barmoqlar o'rtasi (ko'chirish uchun)

    const ikkitasi = () => [...barmoqlar.values()].slice(0, 2);
    const oraliq = ([a, b]) => Math.hypot(a.x - b.x, a.y - b.y);
    const orta = ([a, b]) => ({
      clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2,
    });

    el.addEventListener('pointerdown', (e) => {
      barmoqlar.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (barmoqlar.size >= 2) {
        // Ikkinchi barmoq qo'yildi — aylantirishni to'xtatamiz.
        const juft = ikkitasi();
        pinchMasofa = oraliq(juft);
        const o = orta(juft);
        pinchOrta = { x: o.clientX, y: o.clientY };
        suriladi = false;
        this.surildi = true;   // keyin "bosildi" deb hisoblanmasin
        return;
      }
      suriladi = true;
      suradi = e.shiftKey || e.button === 1;
      this.surildi = false;
      oxirgi = { x: e.clientX, y: e.clientY };
      el.setPointerCapture(e.pointerId);
      el.style.cursor = suradi ? 'move' : 'grabbing';
    });

    const barmoqUzildi = (e) => {
      barmoqlar.delete(e.pointerId);
      if (barmoqlar.size < 2) { pinchMasofa = 0; pinchOrta = null; }
    };

    el.addEventListener('pointermove', (e) => {
      if (barmoqlar.has(e.pointerId)) {
        barmoqlar.set(e.pointerId, { x: e.clientX, y: e.clientY });
      }
      if (pinchMasofa && barmoqlar.size >= 2) {
        const juft = ikkitasi();
        const o = orta(juft);
        const yangiOrta = { x: o.clientX, y: o.clientY };

        // 1) Ko'chirish — barmoqlar birga surilgani. Zoomdan OLDIN, chunki
        //    `_kochir` hozirgi kamera holatiga tayanadi.
        if (pinchOrta) this._kochir(pinchOrta, yangiOrta);
        pinchOrta = yangiOrta;

        // 2) Zoom — barmoqlar orasi o'zgargani.
        const yangi = oraliq(juft);
        if (yangi > 0) {
          // Barmoqlar ochilsa (yangi > eski) masofa kichrayadi = yaqinlashamiz.
          this.masofaniKopaytir(pinchMasofa / yangi, this._polNuqtasi(o));
          pinchMasofa = yangi;
        }
        return;
      }
      if (!suriladi) return;
      const dx = e.clientX - oxirgi.x;
      const dy = e.clientY - oxirgi.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) this.surildi = true;
      const oldingi = oxirgi;
      oxirgi = { x: e.clientX, y: e.clientY };

      if (suradi) {
        this._kochir(oldingi, oxirgi);
        return;
      }
      // Ikkala o'q ham "polni ushlab tortish" mantig'ida: sahna
      // sichqonchaga ERGASHADI, undan qochmaydi.
      this.orbit.burchak += dx * 0.006;
      this.orbit.balandlik = Math.min(
        1.45, Math.max(0.22, this.orbit.balandlik + dy * 0.005),
      );
    });
    el.addEventListener('pointerup', (e) => {
      barmoqUzildi(e);
      suriladi = false;
      suradi = false;
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      el.style.cursor = 'grab';
    });
    // Telefon qo'ng'iroq qilsa yoki barmoq ekrandan chiqib ketsa
    // `pointerup` kelmaydi — barmoq "yopishib" qolmasin.
    el.addEventListener('pointercancel', (e) => {
      barmoqUzildi(e);
      suriladi = false;
      suradi = false;
    });

    // G'ildirak — KURSOR TURGAN NUQTAGA yaqinlashadi, xarita markaziga emas.
    el.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.zumla(-Math.sign(e.deltaY), this._polNuqtasi(e));
    }, { passive: false });

    // O'rta tugma bosilganda brauzer avtoskrollni ochmasin.
    el.addEventListener('auxclick', (e) => { if (e.button === 1) e.preventDefault(); });

    el.addEventListener('click', (e) => {
      if (this.surildi) return;
      this._bosildi(e);
    });

    // Agent ustida kursor o'zgarsin — bosish mumkinligi bilinsin.
    el.addEventListener('pointermove', (e) => {
      if (suriladi) return;
      if (e.shiftKey) { el.style.cursor = 'move'; return; }
      el.style.cursor = this._agentUstidami(e) ? 'pointer' : 'grab';
    });

    window.addEventListener('resize', () => this._olchamniMoslash());
  }

  _agentUstidami(hodisa) {
    const quti = this.chizuvchi.domElement.getBoundingClientRect();
    const nuqta = new THREE.Vector2(
      ((hodisa.clientX - quti.left) / quti.width) * 2 - 1,
      -((hodisa.clientY - quti.top) / quti.height) * 2 + 1,
    );
    const nur = new THREE.Raycaster();
    nur.setFromCamera(nuqta, this.kamera);
    return nur.intersectObjects(
      [...this.agent3d.values()].map((a) => a.guruh), true,
    ).length > 0;
  }

  _bosildi(hodisa) {
    const quti = this.chizuvchi.domElement.getBoundingClientRect();
    const nuqta = new THREE.Vector2(
      ((hodisa.clientX - quti.left) / quti.width) * 2 - 1,
      -((hodisa.clientY - quti.top) / quti.height) * 2 + 1,
    );
    const nur = new THREE.Raycaster();
    nur.setFromCamera(nuqta, this.kamera);

    const nishonlar = [...this.agent3d.values()].map((a) => a.guruh);
    const kesishgan = nur.intersectObjects(nishonlar, true);
    if (!kesishgan.length) {
      this._tanla(null);
      return;
    }
    let obyekt = kesishgan[0].object;
    while (obyekt && !obyekt.userData.rol) obyekt = obyekt.parent;
    const rol = obyekt?.userData?.rol || null;
    this._tanla(rol);
    if (rol && window.ofisAgentTanlandi) window.ofisAgentTanlandi(rol);
  }

  _tanla(rol) {
    this.tanlangan = rol;
    this.agent3d.forEach((a, r) => a.tanlanganini_belgila(r === rol));
  }

  _olchamniMoslash() {
    const en = this.idish.clientWidth || 800;
    const boy = this.idish.clientHeight || 500;
    this.chizuvchi.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.chizuvchi.setSize(en, boy, false);
    this.kamera.aspect = en / boy;
    this.kamera.updateProjectionMatrix();
  }

  // Kursor turgan joydagi pol nuqtasi (y = 0 tekisligi).
  _polNuqtasi(hodisa) {
    const quti = this.chizuvchi.domElement.getBoundingClientRect();
    const nuqta = new THREE.Vector2(
      ((hodisa.clientX - quti.left) / quti.width) * 2 - 1,
      -((hodisa.clientY - quti.top) / quti.height) * 2 + 1,
    );
    const nur = new THREE.Raycaster();
    nur.setFromCamera(nuqta, this.kamera);
    const natija = new THREE.Vector3();
    const tekislik = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    return nur.ray.intersectPlane(tekislik, natija) ? natija : null;
  }

  // Markazni xarita ichida ushlab turadi — chetga uchib ketmasin.
  _markazniChegarala() {
    this.markaz.x = Math.min(XARITA_ENI, Math.max(0, this.markaz.x));
    this.markaz.z = Math.min(XARITA_BOYI, Math.max(0, this.markaz.z));
    this.markaz.y = 0;
  }

  // Shift + sichqoncha: polni ushlab tortish.
  //
  // Piksellarni taxminiy koeffitsiyent bilan dunyo birligiga aylantirish
  // zumga va qiyalikka qarab xato beradi. Shuning uchun ikkala kursor
  // holatini POLGA proyeksiya qilib, aynan shu farqqa suramiz — bosilgan
  // nuqta barmoq ostida turaveradi, 1:1.
  _kochir(oldingi, hozirgi) {
    const a = this._polNuqtasi({ clientX: oldingi.x, clientY: oldingi.y });
    const b = this._polNuqtasi({ clientX: hozirgi.x, clientY: hozirgi.y });
    if (!a || !b) return;
    this.markaz.x -= b.x - a.x;
    this.markaz.z -= b.z - a.z;
    this._markazniChegarala();
  }

  // `yonalish`: +1 yaqinlashish, -1 uzoqlashish.
  // `nishon` berilsa — o'sha nuqta ekranda joyida qoladi (kursorga zum).
  zumla(yonalish, nishon = null) {
    // G'ildirak — qadamli: bir "shitirlash" = 16%.
    this.masofaniKopaytir(1 - yonalish * 0.16, nishon);
  }

  masofaniKopaytir(koeffitsient, nishon = null) {
    // Uzluksiz zoom: ikki barmoq bilan qanchalik ochilsa, shunchalik.
    // G'ildirak ham shu yerga tushadi — mantiq bitta joyda.
    const eski = this.orbit.masofa;
    const yangi = Math.min(90, Math.max(6, eski * koeffitsient));
    this.orbit.masofa = yangi;
    if (!nishon || eski === yangi) return;

    // Markazni kursor (yoki barmoqlar o'rtasi) tomon shu nisbatda suramiz.
    const ulush = 1 - yangi / eski;
    this.markaz.x += (nishon.x - this.markaz.x) * ulush;
    this.markaz.z += (nishon.z - this.markaz.z) * ulush;
    this._markazniChegarala();
  }

  // --- ma'lumot --------------------------------------------------------------

  yangilaAgentlar(royxat, ishlayotganRollar, oldingiRol) {
    (royxat || []).forEach((malumot) => {
      if (!this.agentlar.has(malumot.rol)) {
        const agent = new OfisAgenti(malumot);
        this.agentlar.set(malumot.rol, agent);
        if (agent.ofisdami) {
          const uch = new Agent3D(agent);
          uch.guruh.userData.rol = malumot.rol;
          uch.guruh.traverse((o) => { o.userData.rol = malumot.rol; });
          this.agent3d.set(malumot.rol, uch);
          this.sahna.add(uch.guruh);
        }
      } else {
        this.agentlar.get(malumot.rol).malumot = malumot;
      }
    });

    // Savol chiqdimi? `aniqlik_kerak` — tizim foydalanuvchidan so'rayapti,
    // `tasdiq_kutilmoqda` — inson tasdig'i kutilyapti. Ikkalasida ham
    // butun jamoa majlis xonasiga yig'iladi.
    let savol = null;
    (royxat || []).forEach((malumot, indeks) => {
      const agent = this.agentlar.get(malumot.rol);
      if (!agent) return;
      const holat = (ishlayotganRollar || new Set()).has(malumot.rol)
        ? 'ishlayapti'
        : malumot.oxirgi_holat;
      if (holat === 'aniqlik_kerak' || holat === 'tasdiq_kutilmoqda') {
        savol = savol || holat;
      }
      // O'rindiq bir marta biriktiriladi va o'zgarmaydi — har
      // yangilanishda agent joyidan joyga sakramasin.
      agent.holatniQoy(holat, majlisOrindigi(indeks));
    });

    if (savol) majlisniBoshla(savol);
    else majlisniTugat();

    // Zanjir: ishini tugatgan agent keyingisining stoliga qarab yuradi.
    // Majlis vaqtida bunday yurish bo'lmaydi — hamma stol atrofida.
    if (!majlisdami() && oldingiRol && oldingiRol !== this._oxirgiTopshirish) {
      this._oxirgiTopshirish = oldingiRol;
      const topshiruvchi = this.agentlar.get(oldingiRol);
      const qabul = [...(ishlayotganRollar || new Set())][0];
      const nishon = qabul && ISH_STOLLARI[qabul];
      if (topshiruvchi && nishon && qabul !== oldingiRol) {
        topshiruvchi.boradi(this._yondagiJoy(nishon.otirish));
      }
    }
  }

  _yondagiJoy([x, y]) {
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [2, 0], [-2, 0]]) {
      if (yuribBoladi(x + dx, y + dy)) return [x + dx, y + dy];
    }
    return null;
  }

  // --- tsikl -----------------------------------------------------------------

  _tsikl() {
    const hozir = performance.now();
    const dt = Math.min(0.05, (hozir - this.oxirgiVaqt) / 1000);
    this.oxirgiVaqt = hozir;

    this.agentlar.forEach((a) => a.yangila(dt));
    this.agent3d.forEach((a) => a.yangila());

    const { burchak, balandlik, masofa } = this.orbit;
    this.kamera.position.set(
      this.markaz.x + Math.cos(burchak) * Math.cos(balandlik) * masofa,
      Math.sin(balandlik) * masofa,
      this.markaz.z + Math.sin(burchak) * Math.cos(balandlik) * masofa,
    );
    this.kamera.lookAt(this.markaz);

    this.chizuvchi.render(this.sahna, this.kamera);
    requestAnimationFrame(() => this._tsikl());
  }
}

// --- panel bilan bog'lanish --------------------------------------------------

window.addEventListener('DOMContentLoaded', () => {
  const idish = document.getElementById('ofis-3d');
  if (!idish) return;

  const sahna = new Ofis3D(idish);
  window.ofisSahna = sahna;

  const plus = document.getElementById('zum-plus');
  const minus = document.getElementById('zum-minus');
  if (plus) plus.onclick = () => sahna.zumla(1);
  if (minus) minus.onclick = () => sahna.zumla(-1);

  // panel.js har yangilanishda shu ilgakni chaqiradi.
  window.ofisYangilandi = (royxat, ishlayotganRollar, oldingiRol) => {
    sahna.yangilaAgentlar(royxat, ishlayotganRollar || new Set(), oldingiRol || null);
  };

  // Modul panel.js dan keyin yuklanadi — o'sha vaqtgacha bo'lgan
  // yangilanishni qo'ldan chiqarmaslik uchun o'zimiz so'raymiz.
  if (typeof window.ofisgaUzat === 'function') window.ofisgaUzat();
});
