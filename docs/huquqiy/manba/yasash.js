// Huquqiy hujjatlarni .docx qilib yasaydi (matn: matn.js).
// Ishga tushirish: node yasash.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Tab, HeadingLevel, AlignmentType, LevelFormat,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, Header, Footer,
  PageNumber, TabStopType,
} = require("docx");
const { VERSIYA, SANA, HUJJATLAR, izoh } = require("./matn");
const { uz } = require("./uz");

const CHIQISH = path.join(__dirname, "..");
const SHRIFT = "Times New Roman";
const KENGLIK = 9355; // A4, chap 3 sm, o'ng 1,5 sm

function runlar(matn, asos = {}) {
  return uz(matn)
    .split(/(\*\*.+?\*\*|\[[^\]]+\])/g)
    .filter(Boolean)
    .map((b) => {
      if (b.startsWith("**")) return new TextRun({ ...asos, text: b.slice(2, -2), bold: true });
      if (b.startsWith("[")) return new TextRun({ ...asos, text: b, highlight: "yellow" });
      return new TextRun({ ...asos, text: b });
    });
}

const BAND = /^(\d+(?:\.\d+)*\.)\s+([\s\S]*)$/;

function paragraf(blok) {
  const { k, t } = blok;
  switch (k) {
    case "T":
      return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 80 },
        children: runlar(t, { bold: true, size: 30 }) })];
    case "IL":
      return [new Paragraph({ alignment: AlignmentType.CENTER, pageBreakBefore: true,
        spacing: { after: 160 }, children: runlar(t, { bold: true, size: 26 }) })];
    case "S":
      return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
        children: runlar(t, { italics: true }) })];
    case "M":
      return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 280 },
        children: runlar(t, { size: 20, color: "595959" }) })];
    case "H":
      return [new Paragraph({ heading: HeadingLevel.HEADING_1, children: runlar(t) })];
    case "L":
      return [new Paragraph({ numbering: { reference: "chiziq", level: 0 }, alignment: AlignmentType.JUSTIFIED,
        spacing: { after: 60 }, children: runlar(t) })];
    case "I":
      return [new Paragraph({
        alignment: AlignmentType.JUSTIFIED, spacing: { before: 80, after: 160 }, indent: { left: 284 },
        shading: { type: ShadingType.CLEAR, fill: "FFF4CE", color: "auto" },
        border: { left: { style: BorderStyle.SINGLE, size: 24, color: "E0A800", space: 8 } },
        children: [new TextRun({ text: uz("Huquqshunos uchun izoh: "), bold: true, size: 22 }), ...runlar(t, { size: 22 })],
      })];
    case "Q":
    case "P": {
      const m = t.match(BAND);
      const asos = k === "Q" ? { bold: true } : {};
      const ortga = k === "Q" ? { before: 200, after: 60 } : { after: 100 };
      if (!m) return [new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: ortga, keepNext: k === "Q", children: runlar(t, asos) })];
      const osish = m[1].length > 5 ? 851 : 709;
      return [new Paragraph({
        alignment: AlignmentType.JUSTIFIED, spacing: ortga, keepNext: k === "Q",
        indent: { left: osish, hanging: osish },
        tabStops: [{ type: TabStopType.LEFT, position: osish }],
        children: [new TextRun({ ...asos, text: m[1] }), new TextRun({ children: [new Tab()] }), ...runlar(m[2], asos)],
      })];
    }
    case "TB": {
      const chegara = { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" };
      const chegaralar = { top: chegara, bottom: chegara, left: chegara, right: chegara };
      return [
        new Table({
          width: { size: KENGLIK, type: WidthType.DXA },
          columnWidths: blok.w,
          rows: blok.r.map((qator, i) => new TableRow({
            tableHeader: i === 0,
            cantSplit: true,
            children: qator.map((katak, j) => new TableCell({
              width: { size: blok.w[j], type: WidthType.DXA },
              borders: chegaralar,
              margins: { top: 60, bottom: 60, left: 100, right: 100 },
              shading: i === 0 ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined,
              children: [new Paragraph({ children: runlar(katak, i === 0 ? { bold: true, size: 22 } : { size: 22 }) })],
            })),
          })),
        }),
        new Paragraph({ spacing: { after: 120 }, children: [] }),
      ];
    }
  }
  throw new Error("Nomaʼlum blok: " + k);
}

function hujjat(nomi, sarlavha, bloklar, tepa) {
  const doc = new Document({
    creator: "Climavent jamoasi",
    title: uz(sarlavha),
    description: uz(tepa),
    styles: {
      default: { document: { run: { font: SHRIFT, size: 24 } } },
      paragraphStyles: [{
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: SHRIFT, size: 24, bold: true, color: "000000" },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 },
      }],
    },
    numbering: {
      config: [{
        reference: "chiziq",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 709, hanging: 360 } } } }],
      }],
    },
    sections: [{
      properties: {
        page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1701, right: 850 } },
      },
      headers: {
        default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: uz(tepa), size: 16, color: "595959" })] })] }),
      },
      footers: {
        default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
          children: [new TextRun({ size: 18, color: "595959", children: [uz("Sahifa "), PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES] })] })] }),
      },
      children: bloklar.flatMap(paragraf),
    }],
  });
  return Packer.toBuffer(doc).then((buf) => {
    fs.writeFileSync(path.join(CHIQISH, nomi), buf);
    console.log("yozildi:", nomi, buf.length, "bayt");
  });
}

const tepa = `Versiya ${VERSIYA} · ${SANA} · izohli nusxa (huquqshunos izohlari saytga chiqmaydi)`;
Promise.all([
  hujjat("00-izoh-va-savollar.docx", "Huquqiy hujjatlar: izoh va savollar", izoh, `Ichki hujjat · ${SANA}`),
  ...HUJJATLAR.map((h) => hujjat(h.fayl, h.sarlavha, h.bloklar, tepa)),
]).catch((e) => { console.error(e); process.exit(1); });
