package news.isnad.app;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.firebase.messaging.FirebaseMessaging;

/**
 * اشتراكُ موضوعِ التحذيرات — **بيدِ القارئِ وحدَه**.
 *
 * كان الاشتراكُ يجري في `onCreate` بلا استئذان، فيستقبلُ الجهازُ التحذيراتِ
 * قبلَ أن يُسأل — وعلى أندرويد ١٢ فأقدم لا يوجدُ إذنُ نظامٍ يوقفُ ذلك أصلًا.
 * وهو ما يناقضُ ما تقولُه سياسةُ الخصوصيّةِ حرفيًّا: «لا تُرسَلُ إشعاراتٌ إلّا
 * بعدَ موافقتِك الصريحة». فصارَ الاشتراكُ لا يحدثُ إلّا من نداءٍ صريحٍ بعدَ
 * ضغطةِ «فعِّلْها»، والإلغاءُ متاحٌ بنفسِ الطريق.
 */
@CapacitorPlugin(name = "SanadPush")
public class SanadPush extends Plugin {

    static final String TOPIC = "alerts";

    /**
     * `subscribeToTopic` تُرجِعُ `Task` تنتهي في خيطٍ خلفيّ — فالحسمُ فورَ النداءِ
     * يُبلِّغُ نجاحًا لم يقعْ بعد. وفي قناةِ التحذيراتِ تحديدًا يعني ذلك قارئًا
     * يظنُّ نفسَه مشتركًا ولا يصلُه إنذار. فالنتيجةُ تُنتظَرُ ثمّ يُحسَمُ النداء.
     */
    @PluginMethod
    public void subscribe(PluginCall call) {
        topic(call, true);
    }

    @PluginMethod
    public void unsubscribe(PluginCall call) {
        topic(call, false);
    }

    private void topic(PluginCall call, boolean join) {
        try {
            FirebaseMessaging fm = FirebaseMessaging.getInstance();
            (join ? fm.subscribeToTopic(TOPIC) : fm.unsubscribeFromTopic(TOPIC))
                .addOnCompleteListener(task -> {
                    if (task.isSuccessful()) {
                        call.resolve();
                    } else {
                        Exception e = task.getException();
                        call.reject((join ? "subscribe" : "unsubscribe") + " failed: "
                                + (e != null ? e.getMessage() : "unknown"));
                    }
                });
        } catch (Throwable e) {
            // بلا إعدادات Firebase تغيبُ التهيئةُ كلُّها — يُبلَّغُ ولا يُنهار
            call.reject((join ? "subscribe" : "unsubscribe") + " unavailable: " + e.getMessage());
        }
    }
}
