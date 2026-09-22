// Climavent huquqiy hujjatlari — YAGONA MANBA.
// Bu fayldan: docx (yasash.js), adminka sahifalari va sayt uchun JSON (eksport.js).
//
// Blok turlari: T sarlavha, S kichik sarlavha, M meta, H bo'lim, IL ilova,
// P paragraf ("1.1. ..." — band), L ro'yxat bandi, TB jadval, Q savol,
// I — huquqshunos uchun ichki izoh (FAQAT docx'da; saytga va adminkaga chiqmaydi).
// **qalin** — docx va adminkada qalin; saytda oddiy matn.
// [kvadrat qavs] — to'ldirilmagan joy. E'lon qilinadigan hujjatlarda QOLMASLIGI kerak
// (eksport.js tekshiradi).

const VERSIYA = "1.0";
const SANA = "15.09.2026";

const OPERATOR = {
  nomi: "«CLIMAVENT» MChJ",
  manzil: "Toshkent shahri, Shota Rustaveli ko'chasi, 115",
  telefon: "+998 90 354 78 88",
  email: "climaventuz@outlook.com",
  ishVaqti: "08:00–17:00",
  sayt: "climavent.uz",
};

const B = {
  T: (t) => ({ k: "T", t }), S: (t) => ({ k: "S", t }), M: (t) => ({ k: "M", t }),
  H: (t) => ({ k: "H", t }), P: (t) => ({ k: "P", t }), L: (t) => ({ k: "L", t }),
  I: (t) => ({ k: "I", t }), Q: (t) => ({ k: "Q", t }), IL: (t) => ({ k: "IL", t }),
  TB: (w, r) => ({ k: "TB", w, r }),
};
const { T, S, M, H, P, L, I, Q, IL, TB } = B;

const O = OPERATOR;
const META = `Versiya ${VERSIYA} · E'lon qilingan va kuchga kirgan sana: ${SANA}`;
const ALOQA = `telefon ${O.telefon}, elektron pochta ${O.email}`;

// ═══════════════════════ 01 · SOTUVCHILAR UCHUN OFERTA ═══════════════════════
const oferta = [
  T("SOTUVCHILAR UCHUN OMMAVIY OFERTA"),
  S("Climavent marketpleysida (climavent.uz) tovarlarni joylashtirish xizmatlarini ko'rsatish shartnomasi"),
  M(META),
  P(`Ushbu hujjat ${O.nomi} (keyingi o'rinlarda — «Operator») tomonidan Climavent marketpleysida tovar joylashtirmoqchi bo'lgan yuridik shaxslar va yakka tartibdagi tadbirkorlarga (keyingi o'rinlarda — «Sotuvchi») taklif qilinadigan shartnoma shartlarini belgilaydi. Sotuvchi ushbu shartlarni 3-bo'limda belgilangan tartibda qabul qiladi.`),
  I("Operator har bir arizani tekshirib, Sotuvchini o'zi tanlaydi. Shu sababli bu matn Fuqarolik kodeksining 369-moddasi bo'yicha ommaviy oferta emas, balki «oferta qilishga taklif» bo'lishi mumkin: unda Sotuvchi arizasi — oferta, Operator tasdig'i — aksept (370-modda). Hujjat nomi va 3-bo'limni shunga moslab tekshiring."),

  H("1. ATAMALAR"),
  P("1.1. **Platforma** — Operatorga tegishli climavent.uz sayti, uning mobil versiyasi va Sotuvchi kabineti."),
  P("1.2. **Sotuvchi kabineti** — Sotuvchi o'z do'konini, tovarlarini va buyurtmalarini boshqaradigan boshqaruv paneli. Unga climavent.uz saytidagi «Sotuvchi kabinetiga kirish» havolasi orqali kiriladi."),
  P("1.3. **Do'kon** — Sotuvchining Platformadagi sahifasi: nomi, logotipi, tavsifi, aloqa ma'lumotlari va tovarlari."),
  P("1.4. **Kartochka** — tovarning Platformadagi sahifasi: nomi, rasmlari, tavsifi, texnik tavsiflari, modellari (variantlari) va narxi."),
  P("1.5. **Xaridor** — Platformada ro'yxatdan o'tgan va tovarga buyurtma beradigan jismoniy yoki yuridik shaxs."),
  P("1.6. **Buyurtma** — Xaridorning Platforma orqali bir yoki bir nechta tovarni sotib olish haqidagi so'rovi."),
  P("1.7. **Tarif** — Operator xizmatlarining narxi va to'lov tartibi (1-ilova)."),
  P("1.8. **Aksiya** — Sotuvchi belgilangan muddatga tovarga oddiy narxdan past narx qo'yishi."),
  P("1.9. **Ariza** — Sotuvchi bo'lish uchun Platformada to'ldiriladigan shakl (2-ilova)."),
  P("1.10. **Huquq egasi** — tovar belgisi, mualliflik huquqi, patent yoki boshqa intellektual mulk ob'ektiga huquqi bor shaxs yoki uning vakili (4-ilova)."),

  H("2. SHARTNOMA PREDMETI"),
  P("2.1. Operator Sotuvchiga Platformada Do'kon ochish, Kartochkalarni joylashtirish, Xaridorlardan Buyurtmalar qabul qilish va ularni Sotuvchiga yetkazish xizmatlarini ko'rsatadi. Sotuvchi ushbu shartlarga rioya qiladi va Tarif bo'yicha haq to'laydi."),
  P("2.2. Operator tovarni sotmaydi va Sotuvchi bilan Xaridor o'rtasidagi oldi-sotdi shartnomasining tarafi hisoblanmaydi. Tovar, uning sifati, narxi, yetkazib berilishi, kafolati va qaytarilishi uchun Sotuvchi javob beradi."),
  P("2.3. Xaridor tovar uchun to'lovni bevosita Sotuvchiga amalga oshiradi. Operator Xaridordan tovar uchun pul qabul qilmaydi."),
  P("2.4. Operator kelajakda Platforma orqali to'lov qabul qilishni joriy etishi mumkin. Bu faqat alohida ilova yoki shartnoma asosida, Sotuvchi uni alohida qabul qilganidan keyin qo'llanadi."),
  I("2.3–2.4-bandlar pul bevosita Sotuvchiga tushadigan modelga mos. Platforma orqali to'lov joriy etilsa, komissiya shartnomasi, my.soliq.uz dagi komissioner, fiskal chek va marketpleyslar reyestri talablari alohida hujjatlashtiriladi (00-izoh, 8-savol)."),

  H("3. SHARTNOMANI TUZISH TARTIBI"),
  P("3.1. O'zbekiston Respublikasi rezidenti bo'lgan yuridik shaxslar va yakka tartibdagi tadbirkorlar Sotuvchi bo'la oladi."),
  P("3.2. Shartlarni qabul qilish uchun Sotuvchi: (a) Platformada Arizani to'ldiradi va 2-ilovada ko'rsatilgan hujjatlarni yuklaydi; (b) ushbu oferta va Maxfiylik siyosati bilan tanishganini va Arizadagi shaxsga doir ma'lumotlar ishlanishiga roziligini tasdiqlovchi belgini qo'yadi; (c) Arizani yuboradi. Belgi oldindan qo'yilmaydi."),
  P("3.3. Operator Arizani 5 ish kuni ichida ko'rib chiqadi va zarur bo'lsa qo'shimcha hujjat so'raydi. Qo'shimcha hujjat so'ralsa, muddat hujjat olingan kundan qayta hisoblanadi."),
  P("3.4. Shartnoma Operator Arizani tasdiqlab, Sotuvchi kabinetini faollashtirgan paytdan tuzilgan hisoblanadi. Operator bu haqda Arizada ko'rsatilgan elektron pochta yoki telefon raqamiga xabar yuboradi."),
  P("3.5. Operator Arizani sababini ko'rsatib rad etishi mumkin: hujjatlar to'liq yoki ishonchli bo'lmasa; tovarlar Platforma toifalariga mos kelmasa; Sotuvchi ilgari shartlarni qo'pol buzgani uchun bloklangan bo'lsa."),
  P("3.6. Operator shartlarning qaysi versiyasi, qachon, qaysi hisob va IP-manzildan qabul qilinganini saqlaydi. Bu yozuvlar shartnoma tuzilganining dalili hisoblanadi."),
  P("3.7. Tasdiqlangan Do'kon nofaol holatda yaratiladi va Xaridorlarga ko'rinmaydi. Sotuvchi Do'kon ma'lumotlarini to'ldirib, kamida 1 ta Kartochka joylashtirgach, Operator Do'konni faollashtiradi."),

  H("4. SOTUVCHINING MAJBURIYATLARI"),
  P("4.1. Arizada va Sotuvchi kabinetida to'g'ri va dolzarb ma'lumot berish. Rekvizitlar, rahbar yoki aloqa ma'lumotlari o'zgarsa, 5 ish kuni ichida yangilash."),
  P("4.2. Kartochkalarda tovar haqida to'liq va ishonchli ma'lumot berish: nomi, ishlab chiqaruvchisi, modeli, asosiy texnik tavsiflari, kafolat muddati va shartlari, montaj talab qilinishi. Rasmlar joylashtirilgan tovarga mos bo'lishi kerak."),
  P("4.3. Faqat qonuniy muomalada bo'lgan, zarur sertifikat va ruxsatnomalarga ega tovarlarni joylashtirish (3-ilova). Operator so'rasa, muvofiqlik sertifikati, tovar kelib chiqishini yoki brend egasining ruxsatini tasdiqlovchi hujjatni 3 ish kuni ichida taqdim etish."),
  P("4.4. Narx va mavjudlik ma'lumotini dolzarb saqlash. Tovar tugasa, Kartochkani yashirish yoki «mavjud emas» deb belgilash."),
  P("4.5. Buyurtma haqida xabar olgach, ish kunlari 24 soat ichida Xaridor bilan bog'lanib, Buyurtmani tasdiqlash yoki rad etish. Buyurtma holatini Sotuvchi kabinetida o'z vaqtida yangilash: yangi, to'langan, yetkazilmoqda, bajarildi, bekor qilindi."),
  P("4.6. Xaridorga qonunchilik talab qiladigan hujjatlarni berish: fiskal chek, yuridik shaxslarga hisob-faktura, kafolat taloni va boshqalar."),
  P("4.7. Tovarni qaytarish, almashtirish va kafolat bo'yicha Xaridor talablarini qonunchilikka muvofiq o'zi hal qilish."),
  P("4.8. Xaridor ma'lumotlaridan faqat 9-bo'limda belgilangan maqsadlarda foydalanish."),
  P("4.9. Soxta sharh yozmaslik va yozdirmaslik, sharh uchun Xaridorga haq yoki chegirma taklif qilmaslik, boshqa Sotuvchilarning tovarlariga soxta Buyurtma bermaslik."),
  P("4.10. Sotuvchi kabineti login va parolini boshqalarga bermaslik. Kabinetda Sotuvchi hisobidan qilingan harakatlar Sotuvchi tomonidan qilingan hisoblanadi."),
  P("4.11. Tarif bo'yicha haqni o'z vaqtida to'lash."),
  P("4.12. Huquq egasi shikoyati bo'yicha Operator so'roviga 4-ilovada belgilangan muddatda javob berish."),

  H("5. OPERATORNING MAJBURIYATLARI"),
  P("5.1. Platformaning uzluksiz ishlashi uchun oqilona choralar ko'rish va rejali texnik ishlar haqida imkon qadar oldindan xabar berish."),
  P("5.2. Buyurtmalarni Sotuvchi kabinetiga darhol yetkazish."),
  P("5.3. Sotuvchiga o'z savdosi bo'yicha statistikani ko'rish va eksport qilish imkonini berish."),
  P("5.4. Bir Sotuvchining savdo ma'lumotlari, xaridorlari va narx siyosatini boshqa Sotuvchilarga oshkor qilmaslik (9.4-band)."),
  P("5.5. Sotuvchi murojaatlariga 2 ish kuni ichida javob berish."),
  P("5.6. Shartlar o'zgarishi haqida 12-bo'limda belgilangan muddatda oldindan xabar berish."),

  H("6. KARTOCHKALAR, KONTENT VA MODERATSIYA"),
  P("6.1. Kartochka mazmuni (matn, rasm, tovar belgisi, texnik hujjatlar) uchun Sotuvchi javob beradi va unga huquqi borligini kafolatlaydi."),
  P("6.2. Sotuvchi Operatorga kontentdan Platformada ko'rsatish va Platformani reklama qilish (sayt, ijtimoiy tarmoqlar, reklama materiallari) uchun bepul, noeksklyuziv foydalanish huquqini beradi. Bu huquq shartnoma amal qiladigan davrda va u tugaganidan keyin 6 oy davomida amal qiladi."),
  P("6.3. Operator Kartochka mazmunini o'zgartirmagan holda uni texnik tartibga solishi mumkin: to'g'ri toifaga joylashtirish, rasm o'lchamini moslash, formatlash."),
  P("6.4. Kartochka 3-ilovaga yoki qonunchilikka zid bo'lsa, Huquq egasidan 4-ilovadagi tartibda shikoyat kelsa yoki ma'lumot noto'g'riligi aniqlansa, Operator uni sababini ko'rsatib yashirishi mumkin. Sotuvchi kamchilikni tuzatgach, Kartochka qayta ko'rsatiladi."),
  P("6.5. Xaridorlar sharh va baho qoldirishi mumkin. Sotuvchi sharhni o'chira olmaydi. Operator faqat qoidalarga zid sharhlarni (haqorat, spam, shaxsiy ma'lumot, tovarga aloqasi yo'q matn) yashiradi va sharh mazmunini o'zgartirmaydi."),

  H("7. NARXLAR VA AKSIYALAR"),
  P("7.1. Tovar narxini Sotuvchi belgilaydi. Platformada narx milliy valyutada (so'mda) ko'rsatiladi va Xaridor bilan hisob-kitob so'mda amalga oshiriladi."),
  I("Hozir tizimda narx AQSh dollarida kiritiladi va Operator belgilagan kurs bo'yicha so'mga aylantirilib ko'rsatiladi. Valyutani tartibga solish to'g'risidagi qonun respublika ichida sotiladigan tovar narxini chet el valyutasi va shartli birliklarga bog'lashni taqiqlaydi. Bu mexanizm qonunga mosligini birinchi navbatda tekshiring (00-izoh, 1-savol)."),
  P("7.2. Buyurtma berilgan paytda Platformada ko'rsatilgan narx amal qiladi. Narx texnik xato tufayli noto'g'ri ko'rsatilgan bo'lsa, Sotuvchi Buyurtmani tasdiqlashdan oldin Xaridorga xabar beradi. Bu holda Xaridor Buyurtmani bekor qilishi mumkin."),
  P("7.3. Sotuvchi Aksiya narxini boshlanish va tugash sanasi bilan belgilashi mumkin. Aksiya narxi oddiy narxdan past bo'lishi kerak."),
  P("7.4. Kartochkada chizib ko'rsatiladigan oddiy narx Aksiyadan oldin haqiqatda qo'llangan narx bo'lishi shart. Aksiya oldidan narxni sun'iy oshirib, keyin chegirma ko'rsatish taqiqlanadi."),
  P("7.5. Aksiya muddatida berilgan Buyurtma, Aksiya keyinroq tugagan bo'lsa ham, Aksiya narxida bajariladi."),

  H("8. TARIF VA HISOB-KITOBLAR"),
  P("8.1. Operator xizmatlarining narxi va to'lov tartibi 1-ilovada belgilanadi."),
  P("8.2. Haq so'mda, Operatorning elektron hisob-fakturasi asosida, Operator hisob raqamiga bank o'tkazmasi orqali to'lanadi."),
  P("8.3. Tarif to'lovi 10 kalendar kundan ortiq kechiksa, Operator oldindan xabar berib, to'lov amalga oshirilgunga qadar Do'konni vaqtincha nofaol qilishi mumkin. Bunda ilgari qabul qilingan Buyurtmalar bajarilishi shart."),
  P("8.4. Pullik Tarif davrida har oy yakuni bo'yicha taraflar elektron raqamli imzo bilan Didox yoki taraflar kelishgan boshqa elektron hujjat almashinuvi tizimi orqali xizmatlar ko'rsatilganligi to'g'risidagi dalolatnomani rasmiylashtiradi. Sotuvchi 5 ish kuni ichida imzolamasa yoki asosli e'tiroz bildirmasa, xizmatlar qabul qilingan hisoblanadi."),

  H("9. SHAXSIY MA'LUMOTLAR VA MAXFIYLIK"),
  P("9.1. Buyurtmani bajarish uchun Sotuvchi Xaridorning ismi, telefon raqami, yetkazib berish manzili va Buyurtma tarkibini oladi. Bu ma'lumotlarni ishlash uchun Sotuvchi «Shaxsga doir ma'lumotlar to'g'risida»gi qonun bo'yicha mustaqil javob beradi."),
  P("9.2. Sotuvchi Xaridor ma'lumotlaridan faqat Buyurtmani bajarish, kafolat va qaytarish masalalari uchun foydalanadi. Ularni uchinchi shaxslarga berish, Xaridorning alohida roziligisiz reklama yuborish va boshqa maqsadlarda ishlatish taqiqlanadi."),
  P("9.3. Sotuvchi kabinetida Sotuvchi faqat o'z tovarlariga tegishli Buyurtma, savat, sevimlilar, sharh va xaridor ma'lumotlarini ko'radi."),
  P("9.4. Operator bir Sotuvchining savdo hajmi, xaridorlari, narxlari va boshqa tijorat ma'lumotlarini boshqa Sotuvchilarga bermaydi. Operator bu ma'lumotlardan faqat Platformani yuritish va Sotuvchini aniqlab bo'lmaydigan umumlashtirilgan statistika uchun foydalanadi. Operator yoki unga aloqador shaxslar Platformada Sotuvchi sifatida ishtirok etsa ham, bu qoida to'liq qo'llanadi."),
  I("9.4-band ishlab chiqaruvchilar ishonchi uchun muhim: Operator («CLIMAVENT» MChJ) Platformada «Climavent» do'koni sifatida o'zi ham sotadi. Matnni mustahkamlashni ko'rib chiqing."),
  P("9.5. Taraflar shartnoma doirasida olingan tijorat sirini shartnoma amal qilgan davrda va u tugaganidan keyin 3 yil davomida oshkor qilmaydi, qonunda belgilangan hollar bundan mustasno."),
  P("9.6. Sotuvchi Arizada va Sotuvchi kabinetida ko'rsatgan rahbar, mas'ul shaxs va boshqa xodimlarning shaxsga doir ma'lumotlarini Operatorga ularning roziligi bilan beradi. Operator bu ma'lumotlarni Maxfiylik siyosatiga muvofiq ishlaydi."),

  H("10. JAVOBGARLIK"),
  P("10.1. Taraflar majburiyatlarini bajarmagani yoki lozim darajada bajarmagani uchun O'zbekiston Respublikasi qonunchiligiga muvofiq javob beradi."),
  P("10.2. Sotuvchi tovarning sifati, xavfsizligi, sertifikatlanganligi, Kartochkadagi ma'lumot to'g'riligi, intellektual mulk huquqlariga rioya qilinishi va o'z soliq majburiyatlari uchun javob beradi."),
  P("10.3. Sotuvchi aybi bilan uchinchi shaxslar (Xaridorlar, Huquq egalari, davlat organlari) Operatorga talab qo'ysa, Sotuvchi Operatorga yetkazilgan va hujjat bilan tasdiqlangan zararni qoplaydi."),
  P("10.4. Operator Sotuvchi va Xaridor o'rtasidagi shartnoma bajarilishi uchun javob bermaydi. Operatorning ushbu shartnoma bo'yicha javobgarligi Sotuvchi oxirgi 3 oyda to'lagan Tarif summasi bilan cheklanadi, qasddan qilingan harakatlar bundan mustasno."),
  P("10.5. Yengib bo'lmaydigan kuch (fors-major) holatlari tufayli majburiyatni bajara olmagan taraf javobgarlikdan ozod bo'ladi. Bunday holat haqida ikkinchi taraf 5 ish kuni ichida xabardor qilinadi."),

  H("11. DO'KONNI CHEKLASH VA SHARTNOMANI BEKOR QILISH"),
  P("11.1. Buyurtmalarga javob berilmasa, asosli shikoyatlar takrorlansa, Kartochkalarda noto'g'ri ma'lumot bo'lsa yoki Tarif to'lanmasa, Operator Sotuvchidan kamchilikni 5 ish kuni ichida tuzatishni elektron shaklda, sababini ko'rsatib talab qilishi mumkin."),
  P("11.2. Kamchilik belgilangan muddatda tuzatilmasa, Operator Do'konni nofaol qilishi mumkin. Nofaol Do'kon va uning tovarlari Platformada ko'rinmaydi."),
  P("11.3. Operator Do'konni darhol nofaol qilishi mumkin, agar: soxta hujjat taqdim etilsa; qalbaki yoki taqiqlangan tovar joylashtirilsa; Xaridor ma'lumotlari 9-bo'limga zid ishlatilsa; Platformaga yoki boshqa foydalanuvchilarga zarar yetkazuvchi harakat qilinsa."),
  P("11.4. Sotuvchi Sotuvchi kabineti yoki elektron pochta orqali 14 kalendar kun oldin xabar berib, shartnomani istalgan vaqtda bekor qilishi mumkin."),
  P("11.5. Operator shartnomani 30 kalendar kun oldin xabar berib, 11.3-banddagi hollarda esa darhol bekor qilishi mumkin."),
  P("11.6. Shartnoma bekor qilinganda ham Sotuvchi qabul qilingan Buyurtmalarni bajaradi, Xaridorlar oldidagi kafolat va qaytarish majburiyatlarini saqlaydi hamda bekor qilish sanasigacha bo'lgan Tarif haqini to'laydi."),
  P("11.7. Oldindan to'langan Tarif haqi qaytarilmaydi, shartnoma Operator aybi bilan bekor qilingan hol bundan mustasno."),

  H("12. SHARTLARNI O'ZGARTIRISH"),
  P("12.1. Operator shartlarni bir tomonlama o'zgartirishi mumkin. Yangi versiya Platformada e'lon qilinadi va kuchga kirishidan kamida 15 kalendar kun oldin Sotuvchi kabineti hamda elektron pochta orqali xabar qilinadi. Pullik Tarif joriy etilganda yoki Tarif oshirilganda bu muddat kamida 30 kalendar kun."),
  P("12.2. Rozi bo'lmagan Sotuvchi yangi versiya kuchga kirgunga qadar shartnomani 11.4-banddagi tartibda bekor qilishi mumkin. Bu holda bekor qilish sanasigacha eski shartlar qo'llanadi."),
  P("12.3. Sotuvchi kabinetiga keyingi kirishda yangi versiyani tasdiqlash so'raladi. Yangi versiya kuchga kirgach kabinetdan foydalanishni davom ettirish uni qabul qilish hisoblanadi."),
  P("12.4. Amaldagi versiya raqami va kuchga kirgan sanasi Platformadagi oferta sahifasida ko'rsatiladi. Oldingi versiyalar Operatorda saqlanadi va Sotuvchi so'rovi bo'yicha taqdim etiladi."),
  I("Bir tomonlama o'zgartirish sharti Fuqarolik kodeksi talablariga va sud amaliyotiga mosligini tekshiring."),

  H("13. XABARNOMALAR VA NIZOLARNI HAL QILISH"),
  P("13.1. Taraflar Sotuvchi kabineti, Arizada ko'rsatilgan elektron pochta va telefon orqali xabar almashadi. Dalolatnoma, hisob-faktura va talabnomalar elektron raqamli imzo bilan Didox yoki taraflar kelishgan boshqa elektron hujjat almashinuvi tizimi orqali yuboriladi."),
  P("13.2. Nizolar muzokara yo'li bilan hal qilinadi. Talabnomaga u olingan kundan boshlab 15 kalendar kun ichida javob beriladi."),
  P("13.3. Kelishuvga erishilmasa, nizo Operator joylashgan yerdagi iqtisodiy sudda ko'rib chiqiladi."),
  P("13.4. Ushbu shartnomaga O'zbekiston Respublikasi qonunchiligi qo'llanadi."),

  H("14. OPERATOR MA'LUMOTLARI"),
  TB([2800, 6555], [
    ["Rekvizit", "Qiymati"],
    ["Nomi", O.nomi],
    ["Manzil", O.manzil],
    ["Telefon", O.telefon],
    ["Elektron pochta", O.email],
    ["Ish vaqti", `Dushanba–juma, ${O.ishVaqti}`],
    ["STIR va bank rekvizitlari", "Operator hisob-fakturasida ko'rsatiladi va Sotuvchi so'rovi bo'yicha taqdim etiladi"],
  ]),
  I("Operator STIR, bank, hisob raqami, MFO, QQS kodi va rahbar F.I.Sh. hali berilmagan. Ular kelgach jadvalga qo'shiladi. Ofertada ular ochiq ko'rsatilishi shartligini tekshiring."),

  // ─── 1-ilova ───
  IL("1-ILOVA. TARIFLAR"),
  P(`1. **Ishga tushirish davri.** Ushbu oferta kuchga kirgan kundan (${SANA}) boshlab pullik Tarif joriy etilgunga qadar Operator xizmatlari barcha Sotuvchilar uchun bepul (0 so'm). Bu davrda Tarif to'lanmaydi, qolgan shartlar to'liq amal qiladi.`),
  P("2. **Pullik Tarif.** Pullik Tarif (oylik obuna) joriy etilsa, uning nomi, narxi, tarkibi va QQS qo'llanishi ushbu ilovaning yangi tahririda e'lon qilinadi va kuchga kirishidan kamida 30 kalendar kun oldin xabar qilinadi (12.1-band). Rozi bo'lmagan Sotuvchi shartnomani bekor qilishi mumkin."),
  P("3. Obuna haqi har oyning 5-sanasigacha, Operator hisob-fakturasi asosida oldindan to'lanadi. Oy o'rtasida ulansa, haq qolgan kunlarga mutanosib hisoblanadi."),
  P("4. **Komissiya.** Hozirgi bosqichda komissiya olinmaydi. Platforma orqali to'lov qabul qilish (2.4-band) joriy etilsa, shu tarzda to'langan Buyurtmalar uchun komissiya alohida ilovada belgilanadi."),
  P("5. **Qo'shimcha xizmatlar.** Pullik qo'shimcha xizmatlar (Kartochkani ro'yxat tepasida ko'rsatish, banner va boshqalar) joriy etilsa, ular alohida ilovada, Sotuvchi ixtiyoriy tanlaydigan xizmat sifatida belgilanadi."),
  I("Obuna tariflari nomi, soni va summasi — biznes qarori, hali qabul qilinmagan. Namuna: Boshlang'ich (50 tagacha Kartochka), Biznes (300 tagacha, Excel eksport, Aksiyalar), Ishlab chiqaruvchi (cheklanmagan, brend bloki)."),

  // ─── 2-ilova ───
  IL("2-ILOVA. ARIZA SHAKLI VA TALAB QILINADIGAN HUJJATLAR"),
  H("2.1. Arizadagi ma'lumotlar"),
  TB([3000, 6355], [
    ["Maydon", "Izoh"],
    ["Huquqiy shakli", "MChJ, AJ, boshqa yuridik shaxs yoki YaTT"],
    ["To'liq nomi", "Davlat ro'yxatidagi kabi"],
    ["STIR", "9 raqam (YaTT uchun JShShIR ham qabul qilinadi)"],
    ["Davlat ro'yxatidan o'tgan sana", ""],
    ["Yuridik manzil", ""],
    ["Rahbar", "F.I.Sh., lavozimi"],
    ["Bank rekvizitlari", "Bank nomi, hisob raqami, bank kodi (MFO)"],
    ["QQS to'lovchisi", "Ha (QQS to'lovchisi kodi) yoki yo'q"],
    ["Mas'ul shaxs", "F.I.Sh., telefon, elektron pochta. Sotuvchi kabineti shu shaxsga ochiladi"],
    ["Do'kon nomi", "Platformada ko'rinadigan nom"],
    ["Faoliyat turi", "Ishlab chiqaruvchi, rasmiy distribyutor, diler yoki boshqa sotuvchi"],
    ["Tovar toifalari va brendlar", "Masalan: konditsionerlar, VRF tizimlari, ventilyatsiya, issiqlik nasoslari"],
    ["Ombor yoki shourum manzili", "Ixtiyoriy"],
    ["Yetkazib berish va montaj hududlari", "Ixtiyoriy"],
  ]),
  H("2.2. Hujjatlar (skan yoki foto, PDF, JPG yoki PNG)"),
  L("**Yakka tartibdagi tadbirkor:** davlat ro'yxatidan o'tganlik guvohnomasi; pasport yoki ID-karta."),
  L("**Yuridik shaxs:** davlat ro'yxatidan o'tganlik guvohnomasi; rahbarni tayinlash to'g'risidagi qaror yoki buyruq; rahbarning pasporti yoki ID-kartasi."),
  L("**Arizani vakil topshirsa:** ishonchnoma."),
  L("**Boshqa ishlab chiqaruvchining brendini sotsa:** distribyutor yoki diler shartnomasi yoki brend egasining ruxsat xati (Operator so'raganda)."),
  L("**Majburiy sertifikatlanadigan tovarlar uchun:** muvofiqlik sertifikatlari (Operator so'raganda)."),
  P("2.3. Operator pasport va ID-karta nusxalarini faqat Sotuvchini tekshirish uchun ishlatadi va Ariza bo'yicha qaror qabul qilinganidan keyin 30 kun ichida o'chiradi, qonunda uzoqroq saqlash talab qilingan hol bundan mustasno."),
  I("Pasport nusxasini so'rash zarurligini va saqlash muddatini shaxsiy ma'lumotlar qonuni bo'yicha tekshiring. Zarur bo'lmasa, rahbar F.I.Sh. va STIR bilan cheklanamiz. Backend pasport fayllarini qarordan 30 kun keyin avtomatik o'chiradi."),

  // ─── 3-ilova ───
  IL("3-ILOVA. TAQIQLANGAN TOVARLAR VA KARTOCHKA TALABLARI"),
  H("3.1. Joylashtirish taqiqlanadi"),
  L("qonunchilikka ko'ra muomaladan chiqarilgan yoki muomalasi cheklangan tovarlar;"),
  L("qalbaki tovarlar, shuningdek huquq egasining roziligisiz boshqa shaxsning tovar belgisi qo'yilgan tovarlar;"),
  L("majburiy sertifikatlanishi lozim bo'lgan, lekin sertifikatlanmagan tovarlar;"),
  L("ishlatilgan yoki qayta tiklangan tovarni yangi sifatida taklif qilish;"),
  L("Operator roziligisiz — Platforma toifalariga (iqlim, ventilyatsiya, isitish uskunalari va ularga aloqador tovar va xizmatlar) mos kelmaydigan tovarlar."),
  H("3.2. Kartochka talablari"),
  L("Rasmlar joylashtirilgan tovarni ko'rsatadi; ularda boshqa marketpleys, sayt yoki raqobatchining logotipi va suv belgisi bo'lmaydi."),
  L("Nom va tavsifda telefon raqami, sayt yoki messenjer havolasi bo'lmaydi. Aloqa ma'lumotlari faqat Do'kon profilidagi maxsus maydonlarda ko'rsatiladi."),
  L("Texnik tavsiflar (quvvat, sovutish va isitish unumdorligi, xizmat ko'rsatish maydoni, elektr ta'minoti, shovqin darajasi va boshqalar) ishlab chiqaruvchi hujjatlariga mos keladi."),
  L("Bir tovarning turli modellari yoki o'lchamlari bitta Kartochkada variant sifatida joylashtiriladi; takroriy Kartochkalar ochilmaydi."),
  L("Kafolat muddati va shartlari hamda montajni kim bajarishi Kartochkada ko'rsatiladi."),
  L("«Eng arzon», «1-raqamli» kabi Xaridorni chalg'itishi mumkin bo'lgan so'zlar tasdiqlovchi asossiz ishlatilmaydi."),

  // ─── 4-ilova ───
  IL("4-ILOVA. HUQUQ EGALARI SHIKOYATLARINI KO'RIB CHIQISH TARTIBI"),
  P(`4.1. Huquq egasi Kartochka uning tovar belgisi, mualliflik huquqi (rasm, matn, texnik hujjat), patenti yoki boshqa intellektual mulk huquqini buzmoqda deb hisoblasa, Operatorga ${O.email} manziliga «Huquq buzilishi» mavzusi bilan shikoyat yuboradi.`),
  P("4.2. Shikoyatda quyidagilar bo'lishi kerak:"),
  L("shikoyatchining nomi yoki F.I.Sh., telefon raqami va elektron pochtasi;"),
  L("huquqni tasdiqlovchi hujjat: tovar belgisi guvohnomasi yoki reyestr raqami, patent, litsenziya shartnomasi; vakil yuborsa — ishonchnoma;"),
  L("buzilish bor deb hisoblangan Kartochka yoki Kartochkalarning havolasi;"),
  L("buzilish nimadan iboratligining qisqa tavsifi;"),
  L("shikoyatdagi ma'lumotlar to'g'ri ekanligi haqida bayonot."),
  P("4.3. Operator shikoyat olingan kundan boshlab 3 ish kuni ichida uning to'liqligini tekshiradi. Shikoyat to'liq bo'lmasa, yetishmayotgan ma'lumot so'raladi va muddat ular olingan kundan hisoblanadi."),
  P("4.4. To'liq shikoyat Sotuvchiga yuboriladi. Sotuvchi uni olgan kundan boshlab 5 ish kuni ichida o'z huquqini tasdiqlovchi hujjatlarni (distribyutor yoki diler shartnomasi, brend egasining ruxsat xati, muvofiqlik sertifikati va boshqalar) taqdim etadi yoki Kartochkani tuzatadi yoxud yashiradi."),
  P("4.5. Buzilish hujjatlardan aniq ko'rinsa (qalbaki tovar, boshqa brend nomi bilan sotish, ruxsatsiz nusxalangan rasm), Operator Kartochkani Sotuvchi javobini kutmasdan vaqtincha yashirishi mumkin."),
  P("4.6. Operator taraflar hujjatlarini ko'rib chiqib, Kartochkani tiklash, tuzatilgan holda tiklash yoki yashirishda qoldirish haqida qaror qabul qiladi va har ikkala tarafga sababini ko'rsatib xabar beradi."),
  P("4.7. Operator intellektual mulk bo'yicha nizoni sud o'rnida hal qilmaydi. Taraflar nizoni sudda hal qilishi mumkin; kuchga kirgan sud qarori Operator tomonidan ijro etiladi."),
  P("4.8. Bir Sotuvchiga nisbatan asosli shikoyatlar takrorlansa, 11-bo'lim qo'llanadi. Ataylab yolg'on shikoyat yuborgan shaxsning keyingi shikoyatlari ko'rib chiqilmasligi mumkin."),
  P("4.9. Xaridorlar va boshqa shaxslar ham qalbaki yoki noto'g'ri ta'riflangan tovar haqida shu manzilga xabar berishi mumkin."),
];

// ═══════════════════════ 02 · XARIDORLAR UCHUN SHARTLAR ═══════════════════════
const xaridor = [
  T("CLIMAVENT PLATFORMASIDAN FOYDALANISH SHARTLARI"),
  S("Xaridorlar va sayt foydalanuvchilari uchun"),
  M(META),

  H("1. UMUMIY QOIDALAR"),
  P(`1.1. Ushbu shartlar ${O.nomi} (keyingi o'rinlarda — «Operator») ga tegishli climavent.uz platformasidan (keyingi o'rinlarda — «Platforma») foydalanish tartibini belgilaydi.`),
  P("1.2. Platforma — marketpleys. Unda tovarlarni mustaqil sotuvchilar — yuridik shaxslar va yakka tartibdagi tadbirkorlar (keyingi o'rinlarda — «Sotuvchi») joylashtiradi. Har bir tovar sahifasida uni qaysi Sotuvchi sotayotgani ko'rsatiladi. Operator ham Platformada «Climavent» do'koni orqali Sotuvchi sifatida ishtirok etadi."),
  P("1.3. Operator boshqa Sotuvchilarning tovarlarini sotmaydi. Tovarni sotib olish shartnomasi Xaridor va shu tovarni sotayotgan Sotuvchi o'rtasida tuziladi."),
  P("1.4. Siz ushbu shartlar va Maxfiylik siyosatini ro'yxatdan o'tish shaklidagi belgini qo'yib yoki Buyurtma berib qabul qilasiz. Shartlarga rozi bo'lmasangiz, ro'yxatdan o'tmang va Buyurtma bermang."),

  H("2. RO'YXATDAN O'TISH"),
  P("2.1. Buyurtma berish, savat, sevimlilar va sharh qoldirish uchun ro'yxatdan o'tish talab qilinadi. Ro'yxatdan o'tish va hisobga kirish telefon raqamingizga yuboriladigan bir martalik SMS-kod orqali amalga oshiriladi."),
  P("2.2. Ro'yxatdan o'tish uchun kamida 18 yoshga to'lgan bo'lish kerak."),
  P("2.3. Siz to'g'ri ma'lumot berishga va SMS-kodni boshqalarga bermaslikka majbursiz. Hisobingizdan qilingan harakatlar siz tomondan qilingan hisoblanadi."),
  P(`2.4. Hisobni o'chirishni ${O.email} ga yozib so'rashingiz mumkin. Qonunda saqlash talab qilingan ma'lumotlar (masalan, Buyurtmalar tarixi) belgilangan muddat davomida saqlanadi.`),

  H("3. SOTUVCHI VA TOVAR HAQIDA MA'LUMOT"),
  P("3.1. Do'kon sahifasida Sotuvchining nomi va aloqa ma'lumotlari, shuningdek to'liq yuridik nomi va STIR ko'rsatiladi."),
  I("Elektron tijorat to'g'risidagi qonun oferta beruvchi shaxsning nomi, manzili va aloqa ma'lumotlarini ko'rsatishni talab qiladi. Backend yuridik nom va STIR ni mehmonga beradi; saytda Do'kon sahifasida ko'rsatish frontend topshirig'iga kiritildi."),
  P("3.2. Tovar tavsifi, rasmlari, texnik tavsiflari, narxi va mavjudligi haqidagi ma'lumotni Sotuvchi beradi va uning to'g'riligi uchun javob beradi. Noto'g'ri ma'lumot haqidagi xabarlaringizni Operator 10-bo'limdagi tartibda ko'rib chiqadi."),

  H("4. NARXLAR"),
  P("4.1. Narxlar so'mda ko'rsatiladi."),
  P("4.2. Aksiya narxi belgilangan muddatda amal qiladi. Aksiya muddatida berilgan Buyurtma Aksiya narxida bajariladi."),
  P("4.3. Narx Sotuvchining texnik xatosi tufayli noto'g'ri ko'rsatilgan bo'lsa, Sotuvchi Buyurtmani tasdiqlashdan oldin sizga xabar beradi. Siz to'g'ri narxga rozi bo'lishingiz yoki Buyurtmani bepul bekor qilishingiz mumkin."),
  P("4.4. «Narxi so'rov bo'yicha» deb belgilangan tovarlar narxi Sotuvchi bilan kelishiladi."),
  P("4.5. Yetkazib berish, montaj va boshqa qo'shimcha xizmatlar narxi tovar narxiga kirmasa, u Sotuvchi bilan alohida kelishiladi."),

  H("5. BUYURTMA"),
  P("5.1. Siz savatdagi tovarlarni tanlab, Buyurtma berasiz. Savatda turli Sotuvchilarning tovarlari bo'lsa, har bir Sotuvchi o'z qismini alohida bajaradi."),
  P("5.2. Buyurtma berilgach, Sotuvchi ish kunlari 24 soat ichida siz bilan bog'lanib, mavjudlik, narx, yetkazib berish va to'lov shartlarini tasdiqlaydi."),
  P("5.3. Oldi-sotdi shartnomasi Sotuvchi Buyurtmani tasdiqlagan paytdan tuzilgan hisoblanadi."),
  I("Tovar kartochkasi Sotuvchining ommaviy ofertasimi (bunda Buyurtma — aksept) yoki oferta qilishga taklifmi — bu bandni Fuqarolik kodeksining 369–370-moddalari va elektron tijorat to'g'risidagi qonun bo'yicha tanlang."),
  P("5.4. Buyurtma holatini profilingizda kuzatishingiz mumkin: yangi, to'langan, yetkazilmoqda, bajarildi, bekor qilindi."),
  P("5.5. Tovar hali yuborilmagan bo'lsa, Sotuvchi bilan bog'lanib, Buyurtmani bekor qilishingiz mumkin. Oldindan to'lov qilingan bo'lsa, Sotuvchi pulni to'lov qilingan usulda qaytaradi."),

  H("6. TO'LOV"),
  P("6.1. Tovar uchun to'lov bevosita Sotuvchiga, u taklif qilgan usulda amalga oshiriladi: bank o'tkazmasi (hisob-varaq yoki hisob-faktura asosida), bank kartasi, to'lov ilovasi yoki naqd pul."),
  P(`6.2. Operator boshqa Sotuvchilarning tovarlari uchun pul qabul qilmaydi. Operator nomidan shaxsiy kartaga pul o'tkazish so'ralsa, bu firibgarlik bo'lishi mumkin — bunday holat haqida ${ALOQA} orqali xabar bering.`),
  P("6.3. Sotuvchi qonunchilikka muvofiq sizga fiskal chek, yuridik shaxslarga esa hisob-faktura beradi."),

  H("7. YETKAZIB BERISH VA MONTAJ"),
  P("7.1. Tovarni Sotuvchi yetkazib beradi. Muddat, narx va usul Sotuvchi bilan kelishiladi."),
  P("7.2. Tovarni qabul qilishda qadoq butunligini, komplektligini va tashqi ko'rinishini tekshiring. Kamchilik bo'lsa, uni yetkazib beruvchi ishtirokida qayd eting."),
  P("7.3. Ko'plab iqlim uskunalari (konditsionerlar, VRF tizimlari, issiqlik nasoslari) malakali montajni talab qiladi. Ishlab chiqaruvchi kafolati montajni kim bajarganiga bog'liq bo'lishi mumkin — shartlarni tovar sahifasida yoki Sotuvchidan aniqlang."),

  H("8. QAYTARISH, ALMASHTIRISH VA KAFOLAT"),
  P(`8.1. Talablar tovarni sotgan Sotuvchiga qo'yiladi. Sotuvchi bilan hal bo'lmasa, ${ALOQA} orqali Operatorga yozing — Operator muloqotga yordam beradi.`),
  P("8.2. **Sifatli tovar.** Iste'molchilarning huquqlarini himoya qilish to'g'risidagi qonunga ko'ra, sifatli nooziq-ovqat tovarini sotib olingan kundan boshlab 10 kun ichida qaytarish yoki almashtirish mumkin. Buning uchun tovar ishlatilmagan va shikastlanmagan, qadog'i va iste'mol xususiyatlari saqlangan bo'lishi hamda xaridni tasdiqlovchi hujjat bo'lishi kerak."),
  I("Montaj qilingan uskunalarga va texnik jihatdan murakkab tovarlarga bu qoida qanday qo'llanishini, masofadan sotishda qo'shimcha talablar bor-yo'qligini tekshiring."),
  P("8.3. **Nuqsonli tovar.** Nuqson aniqlansa, qonunchilikda nazarda tutilgan talablarni qo'yishingiz mumkin: almashtirish, narxni kamaytirish, nuqsonni bartaraf etish, pulni qaytarish va boshqalar. Kafolat muddati va shartlari tovar sahifasida va kafolat talonida ko'rsatiladi."),
  P("8.4. Pul to'lov qilingan usulda qaytariladi, taraflar boshqacha kelishgan hol bundan mustasno."),
  P("8.5. Tovarni tadbirkorlik faoliyati uchun sotib olgan yuridik shaxslar va yakka tartibdagi tadbirkorlarga iste'molchilar huquqlari to'g'risidagi qonun qo'llanmaydi. Ular bilan munosabatlar Sotuvchi bilan tuzilgan shartnoma va Fuqarolik kodeksi bilan tartibga solinadi."),

  H("9. SHARHLAR VA BAHOLAR"),
  P("9.1. Siz sotib olgan yoki ishlatgan tovar haqida sharh va baho qoldirishingiz mumkin."),
  P("9.2. Sharhda haqorat, tahdid, spam, reklama, havola, boshqa shaxslarning shaxsiy ma'lumotlari va tovarga aloqasi yo'q matn bo'lmasligi kerak."),
  P("9.3. Operator bu qoidalarga zid sharhlarni yashirishi mumkin, lekin sharh mazmunini o'zgartirmaydi. Sotuvchi sharhni o'chira olmaydi."),

  H("10. HUQUQ BUZILISHI VA NOTO'G'RI MA'LUMOT HAQIDA XABAR BERISH"),
  P(`10.1. Qalbaki yoki noto'g'ri ta'riflangan tovar, soxta sharh yoki sizning tovar belgingiz, mualliflik huquqingiz yoxud boshqa intellektual mulk huquqingizni buzuvchi Kartochka haqida ${O.email} manziliga «Huquq buzilishi» mavzusi bilan yozing.`),
  P("10.2. Huquq egasi shikoyatiga quyidagilarni qo'shing:"),
  L("nomingiz yoki F.I.Sh., telefon raqami va elektron pochta;"),
  L("huquqni tasdiqlovchi hujjat (tovar belgisi guvohnomasi, patent, litsenziya shartnomasi; vakil yuborsa — ishonchnoma);"),
  L("tovar sahifasining havolasi;"),
  L("buzilish nimadan iboratligining qisqa tavsifi."),
  P("10.3. Operator shikoyatni 3 ish kuni ichida ko'rib chiqishni boshlaydi, Sotuvchidan tushuntirish so'raydi va natija haqida sizga xabar beradi. Buzilish aniq bo'lsa, tovar sahifasi darhol yashirilishi mumkin. Batafsil tartib Sotuvchilar uchun ofertaning 4-ilovasida belgilangan."),
  P("10.4. Operator intellektual mulk bo'yicha nizoni sud o'rnida hal qilmaydi. Kuchga kirgan sud qarori Operator tomonidan ijro etiladi."),

  H("11. TAQIQLANGAN HARAKATLAR"),
  L("soxta Buyurtma berish yoki boshqa shaxs nomidan ro'yxatdan o'tish;"),
  L("Platforma ma'lumotlarini avtomatik yig'ish yoki Platforma ishiga xalaqit beruvchi harakatlar;"),
  L("Sotuvchilar va boshqa foydalanuvchilarni aldash yoki haqoratlash;"),
  L("Platforma kontentini Operator yoki huquq egasining yozma roziligisiz tijorat maqsadida nusxalash;"),
  L("Platforma orqali taqiqlangan kontent tarqatish."),
  P("Bunday harakatlar aniqlansa, Operator hisobni cheklashi mumkin."),

  H("12. JAVOBGARLIK"),
  P("12.1. Operator Platformaning ishlashi uchun oqilona choralar ko'radi, lekin uning uzluksiz va xatosiz ishlashini kafolatlamaydi."),
  P("12.2. Tovarning sifati, yetkazib berilishi, kafolati va Sotuvchi bergan ma'lumot uchun Sotuvchi javob beradi."),
  P("12.3. Ushbu shartlar iste'molchining qonunda belgilangan huquqlarini cheklamaydi."),

  H("13. SHAXSIY MA'LUMOTLAR"),
  P("13.1. Shaxsiy ma'lumotlaringiz Maxfiylik siyosatiga muvofiq ishlanadi: climavent.uz/maxfiylik."),
  P("13.2. Buyurtma berganingizda ismingiz, telefon raqamingiz, yetkazib berish manzilingiz va Buyurtma tarkibi faqat shu tovarni sotayotgan Sotuvchiga beriladi."),

  H("14. YAKUNIY QOIDALAR"),
  P("14.1. Operator shartlarni o'zgartirishi mumkin. Yangi versiya kuchga kirishidan kamida 7 kalendar kun oldin Platformada e'lon qilinadi. O'zgarish ilgari berilgan Buyurtmalarga ta'sir qilmaydi."),
  P("14.2. Nizolar muzokara yo'li bilan, kelishuvga erishilmasa — O'zbekiston Respublikasi qonunchiligiga muvofiq sudda hal qilinadi. Iste'molchi qonunda nazarda tutilgan sudga, jumladan o'zi yashaydigan joydagi sudga murojaat qilishi mumkin."),
  P(`14.3. Operator: ${O.nomi}, manzil: ${O.manzil}. Aloqa: ${ALOQA}, ish vaqti ${O.ishVaqti}.`),
];

// ═══════════════════════ 03 · MAXFIYLIK SIYOSATI ═══════════════════════
const maxfiylik = [
  T("MAXFIYLIK SIYOSATI"),
  S("Climavent platformasida shaxsga doir ma'lumotlarni ishlash tartibi"),
  M(META),

  H("1. UMUMIY QOIDALAR"),
  P(`1.1. Ushbu siyosat ${O.nomi} (keyingi o'rinlarda — «Operator») climavent.uz platformasi (keyingi o'rinlarda — «Platforma») foydalanuvchilarining shaxsga doir ma'lumotlarini qanday yig'ishi, ishlashi, saqlashi va himoya qilishini belgilaydi.`),
  P("1.2. Siyosat «Shaxsga doir ma'lumotlar to'g'risida»gi O'zbekiston Respublikasi Qonuniga muvofiq tuzilgan."),
  P(`1.3. Shaxsga doir ma'lumotlar bo'yicha murojaatlar: ${O.email}, ${O.telefon}. Operator manzili: ${O.manzil}.`),
  I("Butun hujjatni 2026-yil 26-martdagi O'RQ-1125 bilan qonunga (27¹-modda) kiritilgan o'zgarishlarni hisobga olib tekshiring. Operatorda ichki hujjatlar ham bo'lishi kerak: ma'lumotlarni ishlash va himoya qilish to'g'risidagi nizom, mas'ul shaxsni tayinlash buyrug'i. Mas'ul shaxs F.I.Sh. hali belgilanmagan."),

  H("2. QANDAY MA'LUMOTLAR YIG'ILADI"),
  TB([2100, 4255, 3000], [
    ["Kimdan", "Ma'lumotlar", "Qanday olinadi"],
    ["Xaridor", "Ism va familiya, telefon raqami, elektron pochta, viloyat va shahar, yetkazib berish manzili", "Ro'yxatdan o'tish va Buyurtma berishda o'zingiz kiritasiz"],
    ["Xaridor", "Buyurtmalar, savatdagi tovarlar, sevimlilar, sharh va baholar", "Platformadan foydalanish davomida"],
    ["Sotuvchi vakili", "Rahbar va mas'ul shaxsning F.I.Sh., lavozimi, telefoni, elektron pochtasi; rahbarning pasporti yoki ID-karta nusxasi; YaTT uchun STIR yoki JShShIR", "Ariza topshirishda"],
    ["Barcha tashrif buyuruvchilar", "IP-manzil, qurilma va brauzer turi, cookie-fayllar, ko'rilgan sahifalar va tashrif vaqti", "Avtomatik, shu jumladan Google Analytics orqali"],
    ["Murojaat qilganlar", "Murojaat mazmuni va aloqa ma'lumotlari", "Telefon, elektron pochta yoki messenjer orqali yozganda"],
  ]),
  P("2.2. Operator biometrik ma'lumotlarni, shuningdek sog'liq, diniy yoki siyosiy qarashlar kabi maxsus toifadagi ma'lumotlarni yig'maydi. Bank kartasi ma'lumotlari Platformada saqlanmaydi."),

  H("3. MA'LUMOTLAR NIMA UCHUN ISHLATILADI"),
  L("hisob yaratish va unga kirishni ta'minlash;"),
  L("Buyurtmani qabul qilish va uni tovar Sotuvchisiga yetkazish;"),
  L("Sotuvchi arizasini tekshirish va Sotuvchi kabinetini ochish;"),
  L("Buyurtma holati, xavfsizlik va shartlar o'zgarishi haqida xabar berish;"),
  L("murojaatlarga javob berish va nizolarni hal qilish;"),
  L("firibgarlik va Platformaga hujumlarning oldini olish;"),
  L("Platformani yaxshilash uchun umumlashtirilgan statistika tayyorlash;"),
  L("reklama va yangiliklar yuborish — faqat alohida roziligingiz bo'lsa; bu rozilikni istalgan vaqtda qaytarib olishingiz mumkin;"),
  L("qonunchilik talablarini bajarish."),

  H("4. ISHLASH ASOSLARI VA ROZILIK"),
  P("4.1. Ma'lumotlar quyidagi asoslarda ishlanadi: ro'yxatdan o'tishda yoki ariza topshirishda bergan roziligingiz; siz bilan tuzilgan shartnomani bajarish zarurati; Operatorning qonunda belgilangan majburiyatlari."),
  P("4.2. Rozilik ro'yxatdan o'tish va ariza shakllarida alohida belgi bilan beriladi. Belgi oldindan qo'yilmaydi va usiz shaklni yuborib bo'lmaydi."),
  P(`4.3. Rozilikni ${O.email} ga yozib qaytarib olishingiz mumkin. Bu holda hisobingiz o'chiriladi, qonunda saqlash talab qilingan ma'lumotlar bundan mustasno.`),

  H("5. MA'LUMOTLAR KIMGA BERILADI"),
  P("5.1. **Sotuvchiga** — faqat uning tovarlariga oid harakatlaringiz bo'yicha: Buyurtma, savatga qo'shilgan yoki sevimlilarga qo'shilgan tovar, sharh. Bunda Sotuvchi ismingiz, telefon raqamingiz va Buyurtmadagi yetkazib berish manzilini ko'radi. Boshqa Sotuvchilarning tovarlariga oid harakatlaringizni ko'rmaydi."),
  I("Sotuvchi o'z tovari savatda turgan, lekin Buyurtma bermagan Xaridorning ismi va telefonini ko'radi. Buning uchun Xaridordan alohida rozilik kerakmi yoki ro'yxatdan o'tishdagi rozilik yetarlimi — tekshiring (00-izoh, 7-savol)."),
  P("5.2. **Texnik xizmat ko'rsatuvchilarga** — faqat xizmat ko'rsatish uchun zarur hajmda va maxfiylik majburiyati asosida:"),
  L("server va ma'lumotlar bazasi — Railway;"),
  L("sayt va boshqaruv paneli xostingi — Vercel;"),
  L("fayl va rasmlarni saqlash — Cloudflare R2, Cloudinary;"),
  L("SMS-kod yuborish xizmati;"),
  L("tashriflar statistikasi — Google Analytics (Google LLC)."),
  P("5.3. **Davlat organlariga** — qonunda belgilangan hollarda va tartibda."),
  P("5.4. Operator shaxsiy ma'lumotlarni sotmaydi va reklama maqsadida uchinchi shaxslarga bermaydi."),

  H("6. SAQLASH JOYI VA MUDDATI"),
  P("6.1. Ma'lumotlar 5.2-bandda ko'rsatilgan provayderlar serverlarida saqlanadi. Bu serverlarning bir qismi O'zbekiston Respublikasi hududidan tashqarida joylashgan. Operator ma'lumotlarni O'zbekiston Respublikasi hududida saqlash bo'yicha qonunchilik talablariga rioya qiladi."),
  I("Backend (Railway), sayt (Vercel), fayllar (Cloudflare R2, Cloudinary) va Google Analytics — xorijiy provayderlar. O'RQ-1125 dan keyin qaysi ma'lumotlar O'zbekistonda saqlanishi shartligini, chet elda saqlash uchun 27¹-moddaning 3-qismidagi qaysi shart qo'llanishini va Davlat reyestrida ro'yxatdan o'tish kerak-kerakmasligini tekshiring. Javobga qarab 6.1-band va infratuzilma o'zgarishi mumkin."),
  P("6.2. Hisob ma'lumotlari hisob faol bo'lgan davrda va o'chirilganidan keyin 3 yil saqlanadi. Buyurtma va to'lovga oid ma'lumotlar soliq va buxgalteriya qonunchiligida belgilangan muddat saqlanadi."),
  P("6.3. Sotuvchi arizasiga ilova qilingan pasport va ID-karta nusxalari Ariza bo'yicha qaror qabul qilinganidan keyin 30 kun ichida o'chiriladi."),
  P("6.4. Muddat tugagach, ma'lumotlar o'chiriladi yoki shaxsni aniqlab bo'lmaydigan holga keltiriladi."),

  H("7. SIZNING HUQUQLARINGIZ"),
  L("ma'lumotlaringiz ishlanayotgani va ularning tarkibi haqida axborot olish;"),
  L("noto'g'ri ma'lumotni tuzatish;"),
  L("ma'lumotlarni o'chirish yoki ishlashni to'xtatishni talab qilish;"),
  L("rozilikni qaytarib olish;"),
  L("reklama xabarlaridan voz kechish;"),
  L("Operator harakatlari ustidan vakolatli davlat organiga yoki sudga shikoyat qilish."),
  P(`7.2. So'rovingizni ${O.email} ga yuboring. Operator qonunda belgilangan muddatda, lekin 10 kalendar kundan kechiktirmay javob beradi.`),

  H("8. XAVFSIZLIK"),
  P("8.1. Ma'lumotlar tarmoq orqali shifrlangan (HTTPS) holda uzatiladi."),
  P("8.2. Kirish huquqi rollar bo'yicha cheklangan: Sotuvchi faqat o'z tovarlariga oid ma'lumotni ko'radi, Operator xodimlari esa faqat vazifasi uchun zarur ma'lumotga kiradi."),
  P("8.3. Xaridorlar hisobiga parolsiz, telefon raqamiga yuboriladigan bir martalik SMS-kod orqali kiriladi. Sotuvchi kabineti shaxsiy login va parol bilan himoyalangan; parol o'rnatish havolalari bir martalik va muddatli."),
  I("Sotuvchi parollari xeshlanganini va kirishlar jurnali yuritilishini backend jamoasi bilan tasdiqlang, keyin 8.3-bandga qo'shing."),
  P("8.4. Ma'lumotlar sizib chiqqani aniqlansa, Operator qonunchilikda belgilangan tartibda vakolatli organni va zarar ko'rgan foydalanuvchilarni xabardor qiladi."),

  H("9. COOKIE-FAYLLAR"),
  P("9.1. **Zarur cookie-fayllar** hisobga kirishni saqlash, til tanlovini va savatni eslab qolish uchun ishlatiladi. Ularsiz Platforma to'g'ri ishlamaydi, shuning uchun ular uchun rozilik so'ralmaydi."),
  P("9.2. **Analitik cookie-fayllar** (Google Analytics) qaysi sahifalar ko'rilgani va sayt qanday ishlatilishi haqida umumlashtirilgan statistika yig'adi. Ular faqat saytdagi cookie ogohlantirishida roziligingizni bildirganingizdan keyin ishlatiladi."),
  P("9.3. Tanlovingizni istalgan vaqtda sayt pastidagi «Cookie sozlamalari» havolasi orqali o'zgartirishingiz yoki brauzer sozlamalarida cookie-fayllarni o'chirishingiz mumkin. Zarur cookie-fayllar o'chirilsa, Platformaning ayrim funksiyalari ishlamasligi mumkin."),
  P("9.4. Reklama va kuzatuv (retargeting) cookie-fayllari ishlatilmaydi."),

  H("10. VOYAGA YETMAGANLAR"),
  P("10.1. Platforma 18 yoshga to'lmagan shaxslar uchun mo'ljallanmagan. Bunday shaxsning ma'lumoti ota-onasining roziligisiz berilgani aniqlansa, u o'chiriladi."),

  H("11. O'ZGARISHLAR VA ALOQA"),
  P("11.1. Siyosatning yangi versiyasi Platformada e'lon qilinadi. Muhim o'zgarishlar haqida ro'yxatdan o'tgan foydalanuvchilarga xabar beriladi."),
  P(`11.2. Operator: ${O.nomi}, manzil: ${O.manzil}, elektron pochta: ${O.email}, telefon: ${O.telefon}.`),
];

// ═══════════════════════ 00 · IZOH VA SAVOLLAR ═══════════════════════
const izoh = [
  T("HUQUQIY HUJJATLAR: IZOH VA SAVOLLAR"),
  S("Climavent marketpleysi · huquqshunos uchun ichki hujjat"),
  M(`Versiya ${VERSIYA} · ${SANA}`),

  H("1. BU HUJJATLAR NIMA"),
  P(`Quyidagi uch hujjat ${SANA} dan climavent.uz saytida amaldagi matn sifatida e'lon qilindi. Ular ochiq manbalar (qonun matnlari, Uzum Market sotuvchilar qo'llanmasi, soliq va buxgalteriya sharhlari) asosida texnik jamoa tomonidan yozilgan va hali huquqshunos tekshiruvidan o'tmagan. Tekshiruvdan keyin yangi versiya e'lon qilinadi.`),
  L("**01** — Sotuvchilar uchun ommaviy oferta: 1-ilova — tariflar, 2-ilova — ariza va hujjatlar, 3-ilova — taqiqlangan tovarlar, 4-ilova — huquq egalari shikoyatlari."),
  L("**02** — Platformadan foydalanish shartlari: xaridorlar uchun, qaytarish, kafolat va huquq buzilishi haqida xabar berish bilan."),
  L("**03** — Maxfiylik siyosati, cookie-fayllar bilan."),
  P("«Huquqshunos uchun izoh» bloklari saytga chiqmaydi — ular alohida tekshirish kerak bo'lgan joylar."),

  H("2. 1.0 VERSIYADA NIMA O'ZGARDI (14.09.2026 LOYIHASIGA NISBATAN)"),
  L("Operator ma'lumotlari to'ldirildi: «CLIMAVENT» MChJ, manzil, telefon, elektron pochta. STIR va bank rekvizitlari hali berilmagan — «hisob-fakturada ko'rsatiladi» deb yozildi."),
  L("Barcha muddatlar loyihadagi taklif qiymatlari bilan qabul qilindi (masalan, ariza 5 ish kuni, buyurtmaga javob 24 soat)."),
  L("Tariflar: pullik tarif joriy etilgunga qadar bepul; narxlar jadvali olib tashlandi, pullik tarif 30 kun oldin e'lon qilinadi."),
  L("Yangi: ofertaga 4-ilova — huquq egalari shikoyatlarini ko'rib chiqish tartibi; foydalanish shartlariga 10-bo'lim — huquq buzilishi haqida xabar berish."),
  L("Yangi: shaxsga doir ma'lumotlarga rozilik alohida belgi bilan, belgi oldindan qo'yilmaydi (oferta 3.2, maxfiylik 4.2)."),
  L("Yangi: cookie-fayllar zarur va analitik turlarga ajratildi; analitik cookie faqat rozilikdan keyin (maxfiylik 9-bo'lim). Saytda Google Analytics ishlaydi."),
  L("Texnik provayderlar ro'yxati va ma'lumotlar xorijiy serverlarda saqlanishi ochiq yozildi (maxfiylik 5.2, 6.1)."),
  L("Xaridor SMS-kod bilan kirishi, Operator o'zi ham «Climavent» do'koni sifatida sotishi aks ettirildi."),

  H("3. PLATFORMA QANDAY ISHLAYDI"),
  L("climavent.uz — ko'p do'konli marketpleys: iqlim, ventilyatsiya va isitish uskunalari (konditsionerlar, VRF tizimlari, ventilyatorlar, issiqlik nasoslari)."),
  L("Sotuvchilar asosan ishlab chiqaruvchilar va distribyutorlar. Operator («CLIMAVENT» MChJ) ham Platformada o'z do'koni bilan sotadi. Ayrim tovarlar narxi bir necha ming AQSh dollari ekvivalentiga yetadi."),
  L("Xaridorlar — ham jismoniy shaxslar, ham kompaniyalar. Xaridor telefon raqami va SMS-kod bilan ro'yxatdan o'tadi, tovarni savatga soladi, buyurtma beradi, sharh va baho qoldiradi."),
  L("Sotuvchi saytda ariza topshiradi va hujjatlarini yuklaydi; Operator tekshirib tasdiqlaydi, do'kon nofaol holda yaratiladi va sotuvchiga bir martalik parol o'rnatish havolasi beriladi."),
  L("Buyurtma holatlari: yangi, to'langan, yetkazilmoqda, bajarildi, bekor qilindi. Holatni sotuvchi o'z kabinetida o'zgartiradi."),
  L("Sayt orqali onlayn to'lov qabul qilish joriy etilmagan: to'lov sotuvchi bilan kelishiladi."),
  L("Sotuvchi kabinetida faqat o'z tovarlariga oid buyurtma, savat (buyurtma berilmagan savatlar ham), sevimlilar va sharhlarni hamda shu xaridorlarning ismi va telefonini ko'radi. Barcha xaridorlar ro'yxatini faqat Operator ko'radi."),
  L("Narxlar bazada AQSh dollarida saqlanadi va Operator belgilagan kurs bo'yicha so'mga aylantirilib ko'rsatiladi. Muddatli aksiya narxi (chizilgan eski narx bilan) joriy etilgan."),

  H("4. LOYIHADA QABUL QILINGAN BIZNES QARORLARI"),
  TB([2000, 3400, 3955], [
    ["Masala", "Yechim", "Sabab"],
    ["Pul kimga tushadi", "Xaridor bevosita Sotuvchiga to'laydi", "Operator xaridor oldida sotuvchi bo'lib qolmaydi; fiskal chek, marketpleyslar reyestri va to'lov integratsiyasi hozircha kerak emas; kompaniyalar hisob-fakturani haqiqiy sotuvchidan oladi"],
    ["Operator daromadi", "Hozircha bepul, keyin oylik obuna", "Bitimlar ko'pincha telefon orqali yopiladi; pul sayt orqali o'tmasa, komissiyani nazorat qilib bo'lmaydi"],
    ["Komissiya", "Faqat sayt orqali to'lov joriy etilgandan keyin", "Pul Operator orqali o'tganda komissiya avtomatik ushlanadi"],
    ["Kim sotuvchi bo'la oladi", "Faqat yuridik shaxslar va YaTT", "Sotuvchilar — ishlab chiqaruvchi va distribyutorlar; kompaniya xaridorlarga QQS bilan hisob-faktura kerak; o'zini o'zi band shaxs ulgurji savdo qila olmaydi"],
    ["Sotuvchini qabul qilish", "Ariza, tekshiruv, tasdiqlash; do'kon nofaol holda yaratiladi", "Soxta do'kon va qalbaki tovarning oldini olish"],
  ]),

  H("5. HUQUQSHUNOSGA SAVOLLAR"),
  P("Savollar muhimlik tartibida. Matn saytda e'lon qilingan, shuning uchun 1–7-savollarga javob imkon qadar tez kerak."),

  Q("1. Narxni dollarga bog'lash (eng muhim)."),
  P("Valyutani tartibga solish to'g'risidagi qonun respublika ichida sotiladigan tovar narxini chet el valyutasi va shartli birliklarga bog'lashni taqiqlaydi. Bizda narx dollarda saqlanadi, sayt esa uni Operator kursi bo'yicha so'mda ko'rsatadi. Bu ruxsat etiladimi? Yo'q bo'lsa, qanday tuzatish kerak: sotuvchi narxni to'g'ridan-to'g'ri so'mda kiritishi kerakmi? Bu kompaniyalar bilan tuziladigan shartnomalarga qanday ta'sir qiladi?"),

  Q("2. Operator elektron tijorat operatori hisoblanadimi?"),
  P("Vazirlar Mahkamasining 26.12.2024 dagi 885-son qaroriga ko'ra, 2025-yil 1-iyuldan bu faoliyatni faqat O'zbekiston rezidenti bo'lgan yuridik shaxs yuritadi. Bitim tuzishda ishtirok etmay, faqat tovar haqida ma'lumot beruvchilar operator hisoblanmaydi. Platforma buyurtma qabul qiladi, lekin pul qabul qilmaydi. Operator maqomi va majburiyatlari qanday?"),

  Q("3. Sotuvchilar ofertasining huquqiy tuzilishi."),
  P("Operator har bir arizani tekshirib, sotuvchini tanlaydi. Bu ommaviy ofertami (Fuqarolik kodeksi, 369-modda) yoki oferta qilishga taklifmi? Shartnoma qaysi paytda tuziladi (01-hujjat, 3-bo'lim)?"),

  Q("4. Xaridor bilan shartnoma qaysi paytda tuziladi?"),
  P("Tovar kartochkasi sotuvchining ofertasi, buyurtma esa aksept bo'lsa, tovar tugagan holda ham sotuvchi sotishga majbur bo'lib qolmaydimi? Hujjatda shartnoma sotuvchi buyurtmani tasdiqlagan paytdan tuziladi (02-hujjat, 5.3-band)."),

  Q("5. Qaytarish va kafolat."),
  P("Montaj qilingan konditsioner, VRF tizimi yoki issiqlik nasosiga sifatli tovarni 10 kun ichida qaytarish qoidasi qanday qo'llanadi? Texnik jihatdan murakkab tovarlar ro'yxati bormi? Masofadan sotishda qo'shimcha talablar bormi? Kafolatni kim beradi: ishlab chiqaruvchimi yoki sotuvchi?"),

  Q("6. Shaxsiy ma'lumotlarni saqlash joyi."),
  P("O'RQ-1125 (26.03.2026) dan keyin majburiy mahalliy saqlash yopiq ro'yxat bilan cheklangan. Bizning ma'lumotlarimiz (ism, telefon, manzil, buyurtmalar, sotuvchi rahbari pasporti nusxasi) Railway, Vercel, Cloudflare, Cloudinary serverlarida, Google Analytics esa Google'da. Bu mumkinmi, bunda 27¹-moddaning 3-qismidagi qaysi shart qo'llanadi? Davlat reyestrida ro'yxatdan o'tish kerakmi? Rozilik belgisi matni yetarlimi (03-hujjat, 4.2-band)?"),

  Q("7. Sotuvchiga xaridor ma'lumotlarini berish."),
  P("Sotuvchi o'z tovari savatda turgan, lekin buyurtma bermagan xaridorning ismi va telefonini ko'radi. Buning uchun alohida rozilik kerakmi? Sotuvchi bu ma'lumotlarga nisbatan mustaqil operatormi yoki Operator topshirig'i bilan ishlovchi shaxsmi?"),

  Q("8. Kelajakda pulni platforma orqali qabul qilish."),
  P("Tekshirish kerak: komissiya shartnomasi (Fuqarolik kodeksi, 48-bob); sotuvchi my.soliq.uz da Operatorni komissioner sifatida qo'shishi; komitent STIR va IKPU kodi ko'rsatilgan elektron fiskal chek (Vazirlar Mahkamasining 22.08.2022 dagi 471-son qarori); OFD bilan integratsiya va marketpleyslar davlat reyestri; to'lov tashkiloti litsenziyasi kerakmi; komissioner sifatida Operator xaridor oldida kafolat va qaytarish uchun javob beradimi."),

  Q("9. O'zini o'zi band shaxslar."),
  P("PF-50 (19.03.2025) bilan o'zini o'zi band shaxslar faoliyat turlariga «marketpleyslarda tovar va xizmat sotish» qo'shilgan, 2026-yildan esa chakana savdo ro'yxatdan chiqarilgan. Elektron tijorat to'g'risidagi qonun ularga faqat chakana savdoga ruxsat beradi. Faqat YaTT va yuridik shaxslarni qabul qilish qarorida xavf bormi?"),

  Q("10. Tarif va hisob-kitoblar."),
  P("Obunaga QQS qanday qo'llanadi? Tarifni bir tomonlama o'zgartirish sharti (01-hujjat, 12-bo'lim) va dalolatnoma imzolanmasa xizmat qabul qilingan hisoblanishi sharti (8.4-band) haqiqiymi? Operator STIR va bank rekvizitlari ofertada ochiq ko'rsatilishi shartmi (14-bo'lim)?"),

  Q("11. Sharhlar va foydalanuvchi kontenti."),
  P("Operator yashirgan yoki yashirmagan sharh uchun javobgarlik; soxta sharhlarga qarshi choralar; sotuvchining sharhga javob yozish huquqi."),

  Q("12. Kontent, tovar belgilari va shikoyat tartibi."),
  P("Sotuvchi ishlab chiqaruvchi brendi va rasmlaridan foydalanishi; Operatorga reklama uchun litsenziya berish sharti (01-hujjat, 6.2-band) yetarlimi? Huquq egalari shikoyatlari tartibi (01-hujjat, 4-ilova) Operatorni javobgarlikdan himoya qiladimi, muddatlar to'g'rimi?"),

  Q("13. Aksiya belgisi va chizilgan narx."),
  P("«Aksiya» belgisi va chizib ko'rsatilgan eski narx uchun reklama va iste'molchilar huquqlari qonunchiligi talablari: haqiqiy oldingi narx, muddatni ko'rsatish."),

  Q("14. Hujjatlar tili."),
  P("Hujjatlar faqat davlat tilida e'lon qilindi. Sayt uch tilda ishlaydi — rus va ingliz tilidagi tarjima shartmi va u qanday maqomga ega bo'ladi?"),

  Q("15. Cookie va Google Analytics."),
  P("Analitik cookie-fayllar uchun oldindan rozilik olish O'zbekiston qonunchiligida shartmi? Loyihada ehtiyot uchun rozilik olinadi (03-hujjat, 9-bo'lim)."),

  H("6. UZUM MARKET TAJRIBASI"),
  L("Oddiy jismoniy shaxs bilan ishlamaydi: faqat YaTT, yuridik shaxs yoki o'zini o'zi band shaxs."),
  L("Kabinetda shaxsiy ma'lumotlar, huquqiy shakl, hujjatlar va bank rekvizitlari so'raladi."),
  L("Ro'yxatdan o'tish ofertani qabul qilish hisoblanadi."),
  L("Sotuvchi my.soliq.uz da Uzumni komissioner sifatida qo'shadi, chunki xaridor pulini Uzum qabul qiladi."),
  L("Tekshiruv 2–4 kun davom etadi, keyin do'kon profili to'ldiriladi va tovar kartochkalari moderatsiya bilan qo'shiladi."),

  H("7. MANBALAR"),
  L("Uzum Sellers qo'llanmasi: seller.uzum.uz/manual/uz/4.start-working/"),
  L("MoySklad: Uzumda sotish — moysklad.uz/poleznoe/marketplejsy/kak-prodavat-na-uzum/"),
  L("O'RQ-792 «Elektron tijorat to'g'risida»: lex.uz/ru/docs/6213428"),
  L("VMQ-885 bo'yicha sharh: norma.uz/novoe_v_zakonodatelstve/k_operatoram_elektronnoy_kommercii_ustanovleny_novye_trebovaniya"),
  L("Valyutani tartibga solish to'g'risidagi yangi qonun: norma.uz/novoe_v_zakonodatelstve/novyy_zakon_o_valyutnom_regulirovanii_glavnye_izmeneniya"),
  L("Shaxsiy ma'lumotlar, O'RQ-1125: pactum.uz/solutions/personalnye-dannye-uzbekistan"),
  L("Marketpleys va to'lov tashkiloti orqali sotish: buxgalter.uz/publish/doc/text183899"),
  L("Marketpleyslar reyestri va OFD: buxgalter.uz/ru/publish/doc/text183408"),
  L("O'zini o'zi band shaxslar faoliyat turlari (PF-50): buxgalter.uz/publish/doc/text207320"),
  L("Sifatli tovarni qaytarish: gov.uz/ru/advice/74/document/1293"),
];

/** E'lon qilinadigan hujjatlar: kalit — sayt yo'li bilan bir xil nom. */
const HUJJATLAR = [
  { tur: "oferta-sotuvchi", kind: "seller", yol: "/oferta/sotuvchi", fayl: "01-sotuvchilar-uchun-oferta.docx", sarlavha: "Sotuvchilar uchun ommaviy oferta", bloklar: oferta },
  { tur: "foydalanish-shartlari", kind: "buyer", yol: "/foydalanish-shartlari", fayl: "02-xaridorlar-uchun-shartlar.docx", sarlavha: "Platformadan foydalanish shartlari", bloklar: xaridor },
  { tur: "maxfiylik", kind: "privacy", yol: "/maxfiylik", fayl: "03-maxfiylik-siyosati.docx", sarlavha: "Maxfiylik siyosati", bloklar: maxfiylik },
];

module.exports = { VERSIYA, SANA, OPERATOR, HUJJATLAR, izoh };
