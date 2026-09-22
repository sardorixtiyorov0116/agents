/* ============================================================
   JONLI GRAF — fon
   Obsidian graf ko'rinishi, lekin video emas: haqiqiy tugunlar.
   15 ta agent tuguni + markaz + yo'ldosh ma'lumot tugunlari.
   ============================================================ */
(function () {
  "use strict";

  var sekin = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var kanvas = document.getElementById("graf");
  var ktx = kanvas.getContext("2d");
  var K = 0, B = 0, dpr = 1;

  var AGENT_NOMI = [
    "Rustam", "Temur", "Sardor", "Nodira", "Anvar", "Aziza", "Zara",
    "Jasur", "Karim", "Doston", "Laziz", "Malika", "Bekzod", "Nilufar", "Hilola"
  ];

  var tugunlar = [], qirralar = [];

  function yasa() {
    tugunlar = []; qirralar = [];
    // markaz — router
    tugunlar.push({ x: 0.5, y: 0.5, vx: 0, vy: 0, r: 7, tur: 0, faza: 0 });
    // 15 agent — halqa bo'ylab
    for (var i = 0; i < 15; i++) {
      var a = (i / 15) * Math.PI * 2 - Math.PI / 2;
      var rad = 0.235 + (i % 3) * 0.035;
      tugunlar.push({
        x: 0.5 + Math.cos(a) * rad * 0.82,
        y: 0.5 + Math.sin(a) * rad,
        vx: (Math.random() - 0.5) * 0.00013,
        vy: (Math.random() - 0.5) * 0.00013,
        r: 4.2, tur: 1, nom: AGENT_NOMI[i], faza: Math.random() * 6.28
      });
      qirralar.push([0, i + 1]);
    }
    // yo'ldoshlar — bilim bo'laklari, katalog yozuvlari
    var asos = tugunlar.length;
    for (var j = 0; j < 58; j++) {
      var ota = 1 + Math.floor(Math.random() * 15);
      var b = Math.random() * Math.PI * 2;
      var d = 0.055 + Math.random() * 0.11;
      tugunlar.push({
        x: tugunlar[ota].x + Math.cos(b) * d * 0.82,
        y: tugunlar[ota].y + Math.sin(b) * d,
        vx: (Math.random() - 0.5) * 0.00022,
        vy: (Math.random() - 0.5) * 0.00022,
        r: 1.5 + Math.random() * 1.5, tur: 2, faza: Math.random() * 6.28
      });
      qirralar.push([ota, asos + j]);
    }
  }

  function olcham() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    K = kanvas.clientWidth; B = kanvas.clientHeight;
    kanvas.width = K * dpr; kanvas.height = B * dpr;
    ktx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  var RANG = ["53,220,242", "181,140,255", "93,168,202"];
  var t = 0, siljish = 0;

  function chiz() {
    ktx.clearRect(0, 0, K, B);
    t += 0.006;

    var i, n;
    for (i = 1; i < tugunlar.length; i++) {
      n = tugunlar[i];
      n.x += n.vx; n.y += n.vy;
      // markazga yumshoq tortish — tarqab ketmasin
      var dx = n.x - 0.5, dy = n.y - 0.5;
      var uz = Math.sqrt(dx * dx + dy * dy);
      var chek = n.tur === 1 ? 0.30 : 0.42;
      if (uz > chek) { n.vx -= dx * 0.000035; n.vy -= dy * 0.000035; }
      n.vx *= 0.9992; n.vy *= 0.9992;
    }

    // qirralar
    ktx.lineWidth = 1;
    for (i = 0; i < qirralar.length; i++) {
      var a = tugunlar[qirralar[i][0]], b2 = tugunlar[qirralar[i][1]];
      var ax = a.x * K, ay = a.y * B + siljish, bx = b2.x * K, by = b2.y * B + siljish;
      var mas = Math.hypot(ax - bx, ay - by);
      var shf = Math.max(0, 0.19 - mas / 4200);
      if (shf <= 0.004) continue;
      ktx.strokeStyle = "rgba(" + (b2.tur === 1 ? RANG[0] : RANG[2]) + "," + shf + ")";
      ktx.beginPath(); ktx.moveTo(ax, ay); ktx.lineTo(bx, by); ktx.stroke();
    }

    // tugunlar
    for (i = 0; i < tugunlar.length; i++) {
      n = tugunlar[i];
      var x = n.x * K, y = n.y * B + siljish;
      if (y < -80 || y > B + 80) continue;
      var puls = sekin ? 0 : Math.sin(t * 1.5 + n.faza) * 0.5 + 0.5;
      var r = n.r * (1 + puls * 0.14);
      var rang = n.tur === 0 ? RANG[0] : (n.tur === 1 ? RANG[1] : RANG[2]);
      var shf = n.tur === 2 ? 0.2 + puls * 0.16 : 0.5 + puls * 0.3;

      var nur = ktx.createRadialGradient(x, y, 0, x, y, r * 6);
      nur.addColorStop(0, "rgba(" + rang + "," + (shf * 0.5) + ")");
      nur.addColorStop(1, "rgba(" + rang + ",0)");
      ktx.fillStyle = nur;
      ktx.beginPath(); ktx.arc(x, y, r * 6, 0, 6.2832); ktx.fill();

      ktx.fillStyle = "rgba(" + rang + "," + shf + ")";
      ktx.beginPath(); ktx.arc(x, y, r, 0, 6.2832); ktx.fill();
    }
    requestAnimationFrame(chiz);
  }

  /* ============================================================
     NAVIGATSIYA
     ============================================================ */
  var lenta = document.getElementById("lenta");
  var slaydlar = Array.prototype.slice.call(document.querySelectorAll(".slayd"));
  var reyka = document.getElementById("reyka");
  var chiziqcha = document.getElementById("chiziqcha");
  var joriy_el = document.getElementById("joriy");
  var jami_el = document.getElementById("jami");
  var maslahat = document.getElementById("maslahat");
  var joriy = 0;

  jami_el.textContent = String(slaydlar.length).padStart(2, "0");

  slaydlar.forEach(function (s, i) {
    var b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-label", (i + 1) + "-slayd: " + (s.dataset.nom || ""));
    b.addEventListener("click", function () { ket(i); });
    reyka.appendChild(b);
  });
  var nuqtalar = Array.prototype.slice.call(reyka.children);

  function ket(i) {
    i = Math.max(0, Math.min(slaydlar.length - 1, i));
    slaydlar[i].scrollIntoView({ behavior: sekin ? "auto" : "smooth" });
  }

  /* Faqat yaqindagi slayd videosi o'ynaydi.
     JONLI XATO (2026-08-30): bu blok `eng !== joriy` ichida edi, shuning
     uchun BIRINCHI yuklashda hech qachon ishlamasdi va beshala video
     bir vaqtda o'ynardi — protsessor bo'g'ilib, sahifa qotib qolardi. */
  var oxirgi_video = -1;
  function videolarni_boshqar(eng) {
    if (eng === oxirgi_video) return;
    oxirgi_video = eng;
    slaydlar.forEach(function (s, i) {
      var yaqin = Math.abs(i - eng) <= 1;
      Array.prototype.forEach.call(s.querySelectorAll("video"), function (v) {
        if (yaqin) { var p = v.play(); if (p && p.catch) p.catch(function () { }); }
        else if (!v.paused) { v.pause(); }
      });
    });
  }

  function belgila() {
    var eng = 0, engf = Infinity;
    slaydlar.forEach(function (s, i) {
      var q = Math.abs(s.getBoundingClientRect().top);
      if (q < engf) { engf = q; eng = i; }
    });
    if (eng !== joriy) {
      joriy = eng;
      nuqtalar.forEach(function (n, i) {
        n.setAttribute("aria-current", i === eng ? "true" : "false");
      });
      joriy_el.textContent = String(eng + 1).padStart(2, "0");
    }
    videolarni_boshqar(eng);
    chiziqcha.style.width = ((eng / (slaydlar.length - 1)) * 100) + "%";
    siljish = -(lenta.scrollTop / Math.max(1, lenta.scrollHeight)) * 220;
    if (maslahat && lenta.scrollTop > 40) maslahat.style.opacity = "0";
  }

  lenta.addEventListener("scroll", belgila, { passive: true });

  document.addEventListener("keydown", function (e) {
    var k = e.key;
    if (k === "ArrowDown" || k === "PageDown" || k === " " || k === "ArrowRight") {
      e.preventDefault(); ket(joriy + 1);
    } else if (k === "ArrowUp" || k === "PageUp" || k === "ArrowLeft") {
      e.preventDefault(); ket(joriy - 1);
    } else if (k === "Home") { e.preventDefault(); ket(0); }
    else if (k === "End") { e.preventDefault(); ket(slaydlar.length - 1); }
    else if (k === "f" || k === "F") {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen().catch(function () { });
    }
  });

  /* ko'rinish kuzatuvchisi — kirish animatsiyasi.

     Har slayd faollashgach TEKSHIRILADI: 1,5 soniyadan keyin matn
     haqiqatan ko'rinib turibdimi? Yo'q bo'lsa — animatsiya butunlay
     o'chiriladi va hamma narsa darrov ko'rinadi.

     NEGA: brauzer sahifani sekinlashtirsa (fondagi oyna, quvvat
     tejash, zaif kompyuter) CSS animatsiyasining vaqti oqmay qoladi —
     `playState` "running" bo'ladi-yu, `currentTime` 0 da turadi.
     Bunda matn butunlay ko'rinmaydi. Prezentatsiyada bu eng yomon
     nosozlik, shuning uchun tekshiruv HAR slaydga qo'yilgan. */
  function korinishni_tekshir(slayd) {
    setTimeout(function () {
      var el = slayd.querySelector(".kir");
      if (el && parseFloat(getComputedStyle(el).opacity) < 0.9) {
        animatsiyani_ochir();
      }
      Array.prototype.forEach.call(
        slayd.querySelectorAll("[data-qiymat]"), yakuniy);
    }, 1500);
  }

  if ("IntersectionObserver" in window) {
    var kuz = new IntersectionObserver(function (yozuvlar) {
      yozuvlar.forEach(function (y) {
        if (y.isIntersecting && !y.target.classList.contains("faol")) {
          y.target.classList.add("faol");
          korinishni_tekshir(y.target);
        }
      });
    }, { root: lenta, threshold: 0.25 });
    slaydlar.forEach(function (s) { kuz.observe(s); });
  } else {
    slaydlar.forEach(function (s) { s.classList.add("faol"); });
  }

  /* ---- raqamlar sanashi ----
     HTML da HAQIQIY qiymat yozib qo'yilgan (yig.py buni to'ldiradi).
     Sanash faqat bezak: nolga tushirib qaytadan o'sadi. Agar brauzer
     sahifani muzlatsa yoki JS to'xtasa, ekranda TO'G'RI raqam qoladi —
     hech qachon "0" ko'rinib qolmaydi.

     JONLI XATO (2026-08-30): avval boshlang'ich matn "0" edi va sahifa
     fonda yuklanganda rAF muzlab, hamma ko'rsatkich "0" bo'lib qoldi.
     Noto'g'ri raqam ko'rsatgandan ko'ra umuman animatsiya qilmagan afzal. */
  var sanagichlar = Array.prototype.slice.call(
    document.querySelectorAll("[data-qiymat]"));

  function matnla(v, kasr) {
    return v.toLocaleString("ru-RU", {
      minimumFractionDigits: kasr, maximumFractionDigits: kasr
    }).replace(/[ \s]/g, " ");
  }
  function yakuniy(el) {
    el.textContent = matnla(parseFloat(el.dataset.qiymat),
      parseInt(el.dataset.kasr || "0", 10));
  }

  function sana(el) {
    var maqsad = parseFloat(el.dataset.qiymat);
    var kasr = parseInt(el.dataset.kasr || "0", 10);
    if (sekin || !isFinite(maqsad)) { yakuniy(el); return; }
    var boshi = null, davom = 1100;
    el.textContent = matnla(0, kasr);
    function qadam(vaqt) {
      if (boshi === null) boshi = vaqt;
      var p = Math.min(1, (vaqt - boshi) / davom);
      el.textContent = matnla(maqsad * (1 - Math.pow(1 - p, 3)), kasr);
      if (p < 1) requestAnimationFrame(qadam); else yakuniy(el);
    }
    requestAnimationFrame(qadam);
  }

  /* Xavfsizlik to'ri: 6 soniyadan keyin hamma raqam yakuniy holatga. */
  setTimeout(function () { sanagichlar.forEach(yakuniy); }, 6000);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) sanagichlar.forEach(yakuniy);
  });

  if ("IntersectionObserver" in window && !sekin) {
    var sk = new IntersectionObserver(function (yozuvlar) {
      yozuvlar.forEach(function (y) {
        if (y.isIntersecting) { sana(y.target); sk.unobserve(y.target); }
      });
    }, { root: lenta, threshold: 0.6 });
    sanagichlar.forEach(function (e) { sk.observe(e); });
  }

  /* Animatsiya faqat JS ishlaganda yoqiladi — aks holda `.kir`
     elementlari sukut bo'yicha KO'RINADI (uslub.css ga qarang). */
  document.documentElement.classList.add("animatsiya");
  slaydlar[0].classList.add("faol");
  korinishni_tekshir(slaydlar[0]);

  /* ---- XAVFSIZLIK TO'RI ----
     Brauzer sahifani fonda muzlatsa, CSS animatsiyasi yarim yo'lda
     qotib qoladi va MATN KO'RINMAY QOLADI. Prezentatsiyada bu qabul
     qilib bo'lmaydigan holat, shuning uchun ikki qavat himoya bor:
       1) sahifa yashirilsa — animatsiya butunlay o'chiriladi;
       2) 6 soniyadan keyin joriy slayd hali ham xira bo'lsa — o'chiriladi.
     Ikkala holatda ham `.kir` sukut holatiga (ko'rinadigan) qaytadi. */
  function animatsiyani_ochir() {
    document.documentElement.classList.remove("animatsiya");
  }
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) animatsiyani_ochir();
  });
  setTimeout(function () {
    var el = slaydlar[joriy].querySelector(".kir");
    if (el && parseFloat(getComputedStyle(el).opacity) < 0.9) animatsiyani_ochir();
  }, 6000);

  /* `autoplay` atributi qoladi (JS ishlamasa ham video o'ynasin), lekin
     u kechroq ishga tushib, bizning pauzamizni bekor qilardi — shuning
     uchun har `play` hodisasida uzoqdagi video yana to'xtatiladi. */
  Array.prototype.forEach.call(document.querySelectorAll("video"), function (v) {
    v.addEventListener("play", function () {
      var s = v.closest(".slayd");
      if (Math.abs(slaydlar.indexOf(s) - joriy) > 1) v.pause();
    });
  });

  window.addEventListener("resize", olcham);
  yasa(); olcham(); belgila();
  if (sekin) { chiz_bir_marta(); } else { requestAnimationFrame(chiz); }
  function chiz_bir_marta() { var s = requestAnimationFrame; window.requestAnimationFrame = function () { }; chiz(); window.requestAnimationFrame = s; }
})();
