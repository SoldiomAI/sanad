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

    @PluginMethod
    public void subscribe(PluginCall call) {
        try {
            FirebaseMessaging.getInstance().subscribeToTopic(TOPIC);
            call.resolve();
        } catch (Throwable e) {
            // بلا إعدادات Firebase: لا اشتراك، ولا انهيار
            call.reject("subscribe failed: " + e.getMessage());
        }
    }

    @PluginMethod
    public void unsubscribe(PluginCall call) {
        try {
            FirebaseMessaging.getInstance().unsubscribeFromTopic(TOPIC);
            call.resolve();
        } catch (Throwable e) {
            call.reject("unsubscribe failed: " + e.getMessage());
        }
    }
}
