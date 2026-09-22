// matn.js dan e'lon qilinadigan JSON yasaydi:
//  1) adminka: climavent-marketplace-admin/src/content/huquqiy/<tur>.json
//     { tur, kind, yol, versiya, sana, sarlavha, bloklar, sayt }
//     bloklar — adminka sahifasi uchun (I va M olib tashlangan),
//     sayt — climavent.uz dagi LegalDoc komponenti shaklida.
//  2) docs/huquqiy/sayt/<tur>.json — frontchi uchun o'sha `sayt` qismi.
// Ishga tushirish: node eksport.js
const fs = require("fs");
const path = require("path");
const { VERSIYA, SANA, HUJJATLAR } = require("./matn");
const { uz } = require("./uz");

const ADMIN = "D:/AGENTS/climavent-marketplace-admin/src/content/huquqiy";
const SAYT = path.join(__dirname, "..", "sayt");

const qalinsiz = (s) => s.replace(/\*\*(.+?)\*\*/g, "$1");

/** "1. ATAMALAR" -> "Atamalar"; "2-ILOVA. ARIZA SHAKLI" -> "2-ilova. Ariza shakli".
 *  LegalDoc bo'limlarni o'zi raqamlaydi, shuning uchun bo'lim raqami olib tashlanadi. */
function sarlavhaSayt(t, ilova) {
  const matn = ilova ? t : t.replace(/^\d+\.\s+/, "");
  const kichik = matn.toLocaleLowerCase("uz");
  // Gap boshi va "1-ilova. " dan keyingi so'z bosh harf bilan.
  return kichik.replace(/(^|\.\s+)(\p{L})/gu, (_, old, harf) => old + harf.toLocaleUpperCase("uz"));
}

function jadvalQatorlari(r) {
  return r.slice(1).map((q) => {
    const [bosh, ...qolgan] = q.filter((k) => k && k.trim());
    return qolgan.length ? `${bosh} — ${qolgan.join("; ")}` : bosh;
  });
}

/** Bloklar -> { intro, sections: [{ h, body: (string | string[])[] }] } */
function saytShakli(bloklar) {
  const intro = [];
  const sections = [];
  let joriy = null;
  let royxat = null;
  const qosh = (x) => {
    if (joriy) joriy.body.push(x);
    else if (typeof x === "string") intro.push(x);
  };
  for (const b of bloklar) {
    if (b.k !== "L") royxat = null;
    switch (b.k) {
      case "H":
        // Ilova ichidagi "2.1. ..." kichik sarlavhalar — bo'lim ichida matn qatori.
        if (/^\d+\.\d+\./.test(b.t) && joriy) qosh(qalinsiz(b.t) + ":");
        else sections.push((joriy = { h: sarlavhaSayt(b.t, false), body: [] }));
        break;
      case "IL":
        sections.push((joriy = { h: sarlavhaSayt(b.t, true), body: [] }));
        break;
      case "P":
        qosh(qalinsiz(b.t));
        break;
      case "L":
        if (!royxat) {
          royxat = [];
          qosh(royxat);
        }
        royxat.push(qalinsiz(b.t));
        break;
      case "TB":
        qosh(jadvalQatorlari(b.r).map(qalinsiz));
        break;
      default:
        break; // T, S, M, I — saytga chiqmaydi
    }
  }
  return { intro: intro.join(" "), sections };
}

const uzChuqur = (x) => (typeof x === "string" ? uz(x) : Array.isArray(x) ? x.map(uzChuqur) : Object.fromEntries(Object.entries(x).map(([k, v]) => [k, uzChuqur(v)])));

fs.mkdirSync(ADMIN, { recursive: true });
fs.mkdirSync(SAYT, { recursive: true });

let xato = false;
for (const h of HUJJATLAR) {
  const ochiq = h.bloklar.filter((b) => b.k !== "I" && b.k !== "M");
  const matnlar = ochiq.flatMap((b) => [b.t ?? "", ...(b.r ?? []).flat()]).join("\n");
  const qoldiq = matnlar.match(/\[[^\]]*\]/g);
  if (qoldiq) {
    console.error(`✗ ${h.tur}: to'ldirilmagan joy qoldi: ${qoldiq.join(", ")}`);
    xato = true;
  }
  const sayt = uzChuqur(saytShakli(ochiq));
  const bloklar = ochiq.map((b) => ({ ...b, t: b.t === undefined ? undefined : uz(b.t), r: b.r ? b.r.map((q) => q.map(uz)) : undefined }));
  const umumiy = { tur: h.tur, kind: h.kind, yol: h.yol, versiya: VERSIYA, sana: SANA, sarlavha: uz(h.sarlavha) };
  fs.writeFileSync(path.join(ADMIN, `${h.tur}.json`), JSON.stringify({ ...umumiy, bloklar, sayt }, null, 1) + "\n");
  // Frontchi uchun: sayt modulidagi { uz, ru, en } shakliga to'g'ridan-to'g'ri mos.
  const saytFayl = { ...umumiy, uz: sayt, ru: { intro: "", sections: [] }, en: { intro: "", sections: [] } };
  fs.writeFileSync(path.join(SAYT, `${h.tur}.json`), JSON.stringify(saytFayl, null, 1) + "\n");
  console.log(`✓ ${h.tur}: ${sayt.sections.length} bo'lim, ${bloklar.length} blok`);
}
if (xato) process.exit(1);
