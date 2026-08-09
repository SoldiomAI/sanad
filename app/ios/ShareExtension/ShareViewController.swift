import UIKit
import Social
import MobileCoreServices
import UniformTypeIdentifiers

/// «شارِكْ إلى سَنَد» — امتدادُ المشاركة.
///
/// هذا هو الجوابُ على قاعدةِ آبل 4.2: قدرةٌ لا مقابلَ لها على الويب إطلاقًا —
/// أن يصيرَ فحصُ الإسنادِ فِعلًا على مستوى نظامِ التشغيل. تشاركُ أيَّ رابطٍ من
/// أيِّ تطبيقٍ إلى سَنَد، فيصدرُ فيه حُكمُ إسناد.
///
/// الامتدادُ **لا يفحصُ بنفسِه** ولا يتّصلُ بالشبكة: يستخرجُ الرابطَ ويُسلّمُه
/// للتطبيقِ الأمِّ عبرَ `sanad://verify?u=…`. امتدادُ المشاركةِ يعملُ في عمليّةٍ
/// مقيَّدةِ الذاكرةِ يقتلُها النظامُ بلا رحمة، فإبقاؤه رقيقًا هو ما يجعلُه موثوقًا —
/// والفحصُ نفسُه يبقى في مكانٍ واحدٍ لا مكانَين.
class ShareViewController: UIViewController {

    override func viewDidLoad() {
        super.viewDidLoad()
        extractURL { [weak self] url in
            guard let self = self else { return }
            guard let url = url else {
                self.extensionContext?.completeRequest(returningItems: nil)
                return
            }
            self.openHost(with: url)
            // الإنهاءُ الفوريُّ قد يقتلُ العمليّةَ قبلَ أن يُسلَّمَ الرابطُ للتطبيق،
            // فيبتلعُ النظامُ المشاركةَ صامتًا. مهلةٌ قصيرةٌ تكفي لتسليمِه.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                self.extensionContext?.completeRequest(returningItems: nil)
            }
        }
    }

    /// يقرأُ أوّلَ رابطٍ في العناصرِ المُشارَكة — رابطًا صريحًا أو نصًّا يحويه.
    private func extractURL(_ done: @escaping (String?) -> Void) {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            return done(nil)
        }
        for item in items {
            for provider in item.attachments ?? [] {
                if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                    provider.loadItem(forTypeIdentifier: UTType.url.identifier) { data, _ in
                        DispatchQueue.main.async { done((data as? URL)?.absoluteString) }
                    }
                    return
                }
                if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                    provider.loadItem(forTypeIdentifier: UTType.plainText.identifier) { data, _ in
                        let text = (data as? String) ?? ""
                        DispatchQueue.main.async { done(Self.firstURL(in: text)) }
                    }
                    return
                }
            }
        }
        done(nil)
    }

    /// كثيرًا ما يُشارَكُ الرابطُ داخلَ نصٍّ («شوف هذا … https://…»)، فنلتقطُه منه.
    static func firstURL(in text: String) -> String? {
        guard let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) else {
            return nil
        }
        let range = NSRange(text.startIndex..., in: text)
        return detector.firstMatch(in: text, options: [], range: range)?.url?.absoluteString
    }

    /// يفتحُ التطبيقَ الأمَّ بالرابطِ مُرمَّزًا. الامتدادُ لا يملكُ `UIApplication.shared`،
    /// فيُصعَدُ في سلسلةِ المُستجيبين للوصولِ إلى `open(_:)`.
    ///
    /// ⚠️ قيدٌ معروفٌ يجبُ إغلاقُه قبلَ النشر: مخطَّطُ `sanad://` **ليس محجوزًا**
    /// لتطبيقٍ بعينِه في iOS — أيُّ تطبيقٍ آخرَ يُسجّلُ المخطَّطَ نفسَه قد يلتقطُ
    /// الرابطَ المُشارَك. الحمولةُ هنا رابطُ خبرٍ عامٌّ اختارَ القارئُ مشاركتَه (لا
    /// سرَّ فيها)، لكنّ العلاجَ الصحيحَ **الروابطُ الشاملة (Universal Links)**:
    /// نطاقٌ مقترنٌ + ملفُّ `apple-app-site-association` على isnad.news. وكلاهما
    /// يحتاجُ **Team ID** من حسابِ آبل — وهو غيرُ موجودٍ بعد. يُنفَّذُ فورَ توفّرِه،
    /// ولا يُشحَنُ الامتدادُ للمتجرِ قبلَه.
    private func openHost(with url: String) {
        let encoded = url.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""
        guard let deep = URL(string: "sanad://verify?u=\(encoded)") else { return }
        var responder: UIResponder? = self
        while let r = responder {
            if let app = r as? UIApplication {
                app.perform(#selector(openURL(_:)), with: deep)
                return
            }
            responder = r.next
        }
    }

    @objc private func openURL(_ url: URL) {}
}
