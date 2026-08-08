/* سَنَد — جسرُ الغلافِ الأصليّ. يُحقَنُ في نسخةِ التطبيقِ وحدَها (`app/www`)،
   ولا يُمَسُّ `index.html` الذي يخدمُ الموقع. كلُّ ما هنا يخرجُ صامتًا على الويب.

   ثابتُ الإشعارات: **لا يُرسَلُ إلّا التحذيرُ الرسميُّ**. لا أخبارَ عامّة، ولا
   ترويج، ولا «عُدْ إلينا». الإشعارُ مقاطعةٌ للقارئ، فلا يُنفَقُ إلّا على ما
   يستحقُّ المقاطعة — وهذا أيضًا ما يجعلُ الإذنَ يُمنَحُ ولا يُسحَب.

   ولا يُخزَّنُ رمزُ الجهازِ في أيِّ مكان: الاشتراكُ بـ«موضوعٍ» (topic) لا بجهاز،
   فلا يملكُ الأنبوبُ قائمةَ أجهزةٍ أصلًا — أبسطُ وأسلمُ للخصوصيّة. */
(function () {
  "use strict";
  var Cap = window.Capacitor;
  if (!Cap || !Cap.isNativePlatform || !Cap.isNativePlatform()) return;

  var EN = false;
  try { EN = (localStorage.getItem("sanad_lang") || "") === "en"; } catch (e) {}

  document.documentElement.classList.add("native-app");

  // ── شريطُ الحالة يتبعُ ثيمَ الصفحة ──────────────────────────────────────
  try {
    var SB = Cap.Plugins && Cap.Plugins.StatusBar;
    if (SB) {
      var dark = document.documentElement.getAttribute("data-theme") === "dark";
      SB.setStyle({ style: dark ? "DARK" : "LIGHT" }).catch(function () {});
    }
  } catch (e) {}

  var Push = Cap.Plugins && Cap.Plugins.PushNotifications;
  if (!Push) return;

  var ASKED = "sanad_push_asked";
  function asked() { try { return localStorage.getItem(ASKED) === "1"; } catch (e) { return false; } }
  function markAsked() { try { localStorage.setItem(ASKED, "1"); } catch (e) {} }

  // ── الانتقالُ عند فتحِ الإشعار ───────────────────────────────────────────
  function openAlerts(data) {
    try {
      if (typeof window.setView === "function") {
        window.setView("brief");
        if (typeof window.syncRoute === "function") window.syncRoute();
      }
      var box = document.getElementById("alertWrap");
      if (box && box.scrollIntoView) box.scrollIntoView({ behavior: "smooth", block: "start" });
      // إبرازٌ لحظيٌّ كي يعرفَ القارئُ أيَّ تحذيرٍ فتحَه — لا تنقّلَ أعمى
      if (box) {
        box.style.transition = "box-shadow .4s";
        box.style.boxShadow = "0 0 0 2px var(--gold, #c9a227)";
        setTimeout(function () { box.style.boxShadow = ""; }, 2400);
      }
    } catch (e) {}
  }

  Push.addListener("pushNotificationActionPerformed", function (ev) {
    openAlerts((ev && ev.notification && ev.notification.data) || {});
  }).catch(function () {});

  // إشعارٌ وصلَ والتطبيقُ مفتوح: لا نقاطعُ القارئَ بنافذة — نُحدّثُ البيانات
  // فيظهرُ التحذيرُ في مكانِه الطبيعيّ.
  Push.addListener("pushNotificationReceived", function () {
    try { if (typeof window.load === "function") window.load(); } catch (e) {}
  }).catch(function () {});

  Push.addListener("registrationError", function () {}).catch(function () {});

  function register() {
    Push.register().catch(function () {});
  }

  function requestAndRegister() {
    markAsked();
    Push.requestPermissions().then(function (r) {
      if (r && r.receive === "granted") register();
    }).catch(function () {});
  }

  // إن كان الإذنُ ممنوحًا سلفًا فلا سؤالَ ولا بطاقة — نُسجّلُ فحسب
  Push.checkPermissions().then(function (r) {
    if (r && r.receive === "granted") { register(); return; }
    if (r && r.receive === "denied") return;
    if (!asked()) setTimeout(showOptIn, 1500);
  }).catch(function () {});

  // ── بطاقةُ استئذانٍ صريحةٌ داخلَ الصفحة ──────────────────────────────────
  // لا نفتحُ نافذةَ النظامِ على البارد: نشرحُ أوّلًا ماذا سنُرسِلُ بالضبط، ثمّ
  // نسألُ بلمسةٍ من القارئ. الإذنُ المرفوضُ مرّةً لا يُستعادُ إلّا من الإعدادات.
  function showOptIn() {
    if (document.getElementById("napOptIn")) return;
    var host = document.getElementById("alertWrap") || document.querySelector(".col-main") || document.body;
    var card = document.createElement("div");
    card.id = "napOptIn";
    card.setAttribute("role", "region");
    card.style.cssText =
      "margin:14px 0;padding:14px 16px;border:1px solid var(--line,#00000022);" +
      "border-radius:12px;background:var(--card,#fff);display:flex;gap:12px;" +
      "align-items:flex-start;flex-wrap:wrap";
    var t = document.createElement("div");
    t.style.cssText = "flex:1 1 220px;min-width:0";
    var h = document.createElement("b");
    h.style.cssText = "display:block;margin-bottom:4px";
    h.textContent = EN ? "Official alerts only" : "التحذيراتُ الرسميّةُ وحدَها";
    var p = document.createElement("span");
    p.style.cssText = "color:var(--mut,#555);font-size:13.5px;line-height:1.7";
    p.textContent = EN
      ? "We notify you only when a verified official warning lands — civil defence, interior, aviation, weather. Nothing else. No promotions."
      : "لا نُنبّهُك إلّا حين يصلُ تحذيرٌ رسميٌّ مُسنَد — دفاعٌ مدنيّ، داخليّة، طيران، أرصاد. لا شيءَ سواه، ولا ترويج.";
    t.appendChild(h); t.appendChild(p);
    var actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:8px;align-items:center";
    var yes = document.createElement("button");
    yes.type = "button";
    yes.textContent = EN ? "Enable" : "فعِّلْها";
    yes.style.cssText =
      "min-height:44px;padding:0 16px;border-radius:10px;border:0;cursor:pointer;" +
      "background:var(--gold,#c9a227);color:#111;font:inherit;font-weight:700";
    var no = document.createElement("button");
    no.type = "button";
    no.textContent = EN ? "Not now" : "لاحقًا";
    no.style.cssText =
      "min-height:44px;padding:0 12px;border-radius:10px;cursor:pointer;" +
      "background:transparent;border:1px solid var(--line,#00000022);" +
      "color:var(--mut,#555);font:inherit";
    yes.addEventListener("click", function () { card.remove(); requestAndRegister(); });
    no.addEventListener("click", function () { card.remove(); markAsked(); });
    actions.appendChild(yes); actions.appendChild(no);
    card.appendChild(t); card.appendChild(actions);
    host.insertBefore(card, host.firstChild);
  }
})();
