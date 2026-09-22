// o' g' -> oʻ gʻ, qolgan apostrof -> tutuq belgisi ʼ
const uz = (s) => s.replace(/([oOgG])'/g, "$1ʻ").replace(/'/g, "ʼ");
module.exports = { uz };
