/**
 * يَنسخُ أصولَ الموقعِ الساكنةَ إلى `app/www` ليحملَها التطبيقُ داخلَه.
 *
 * قرارٌ معماريٌّ مقصود: التطبيقُ **لا يشيرُ إلى isnad.news بـ`server.url`**.
 * لسببين، كلاهما جوهريّ:
 *   ١) غلافٌ يفتحُ موقعًا هو بالضبط ما ترفضُه آبل في القاعدة 4.2 («تطبيقٌ
 *      ليس إلّا موقعًا مُعادَ تغليفُه»).
 *   ٢) الغلافُ المحمولُ داخلَ التطبيقِ يعملُ بلا شبكة — وهذا شرطُ القراءةِ
 *      دون اتّصال. البياناتُ وحدَها تُجلَبُ حيّةً، فلا تتعفّنُ الأخبار.
 *
 * قائمةُ النسخِ **مُصرَّحةٌ لا شاملة**: لا يُنسَخُ إلّا ما تحتاجُه الصفحة، كي لا
 * يتسرّبَ `pipeline/` أو `daily/` أو `.git` إلى حزمةٍ تُشحَنُ للمتاجر.
 */
import { cp, mkdir, rm, readFile, writeFile, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const WWW = resolve(HERE, "..", "www");
const SITE = "https://www.isnad.news";

// ما يُنسَخُ حرفيًّا — ولا شيءَ غيرُه
const COPY = [
  "index.html",
  "manifest.webmanifest",
  "og-card.png",
  "icons",
  "fonts",
  "assets",
];

// نفسُ سياسةِ vercel.json، مُطبَّقةً داخلَ الغلافِ الأصليّ. الترويسةُ لا تصلُ
// هنا (الملفّاتُ محلّيّةٌ لا مخدومة)، فتُحقَنُ وسمًا كي لا يكونَ التطبيقُ أرخى
// من الموقعِ أمنًا. `connect-src` هو ما يُبقي البياناتِ حيّةً.
const CSP = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data: https:",
  "media-src 'self' https://raw.githubusercontent.com blob:",
  "font-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net",
  "connect-src 'self' https://raw.githubusercontent.com https://cdn.jsdelivr.net " +
    "https://huggingface.co https://*.huggingface.co https://*.hf.co " +
    "https://cas-bridge.xethub.hf.co https://uewqsczvyglahnqjhuvx.supabase.co " +
    "wss://uewqsczvyglahnqjhuvx.supabase.co https://api.x.ai",
  "worker-src 'self' blob:",
].join("; ");

async function exists(p) {
  try { await stat(p); return true; } catch { return false; }
}

async function main() {
  await rm(WWW, { recursive: true, force: true });
  await mkdir(WWW, { recursive: true });

  for (const item of COPY) {
    const src = join(REPO, item);
    if (!(await exists(src))) {
      console.warn(`⚠️  مفقود، تُخطّى: ${item}`);
      continue;
    }
    await cp(src, join(WWW, item), { recursive: true });
  }

  let html = await readFile(join(WWW, "index.html"), "utf8");

  // ١) سياسةُ الأمانِ وسمًا — الترويسةُ لا تصلُ الملفَّ المحلّيّ
  if (!html.includes("Content-Security-Policy")) {
    html = html.replace(
      /<meta charset=["']?utf-8["']?\s*\/?>/i,
      (m) => `${m}\n<meta http-equiv="Content-Security-Policy" content="${CSP}">`,
    );
  }

  // ٢) عاملُ الخدمةِ لا معنى له داخلَ غلافٍ يحملُ أصولَه أصلًا — وتسجيلُه
  //    تحتَ localhost يُخبّئُ نسخةً ثانيةً تُنافسُ حزمةَ التطبيق.
  html = html.replace(
    /if\("serviceWorker" in navigator\)\{[^\n]*\}/,
    'if("serviceWorker" in navigator && !window.Capacitor){window.addEventListener("load",()=>{navigator.serviceWorker.register("/sw.js").catch(()=>{})});}',
  );

  // ٣) بوّابةُ المؤسساتِ تبقى على الويب — لا تُشحَنُ داخلَ تطبيقٍ عامّ
  html = html.replaceAll('href="/enterprise"', `href="${SITE}/enterprise"`);

  // ٤) جسرُ الإشعارات (يُحقَنُ قبل </body>؛ لا أثرَ له على الويب)
  const bridge = await readFile(join(HERE, "native-bridge.js"), "utf8");
  html = html.replace(/<\/body>/i, `<script>\n${bridge}\n</script>\n</body>`);

  await writeFile(join(WWW, "index.html"), html, "utf8");

  const bytes = html.length;
  console.log(`✅ www جاهز — index.html ${(bytes / 1024).toFixed(0)} ك.ب · ${COPY.length} مدخلًا`);
}

main().catch((e) => {
  console.error("sync-web فشل:", e);
  process.exit(1);
});
