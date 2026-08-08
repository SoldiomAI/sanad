package news.isnad.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    /** قناةُ التحذيراتِ الرسميّة — القناةُ الوحيدة. لا قناةَ ترويجٍ ولا تذكير. */
    private static final String CHANNEL_ID = "sanad_alerts";

    /**
     * موضوعُ الإشعارات. الاشتراكُ بـ«موضوعٍ» لا بجهاز: فلا يُخزَّنُ رمزُ جهازٍ
     * في أيِّ مكان، ولا يملكُ الأنبوبُ قائمةَ أجهزةٍ أصلًا. الأنبوبُ ساكنٌ
     * يكتبُ في مستودع — لا خادمَ لديه يحفظُ الرموزَ ولا ينبغي أن يكون.
     */
    private static final String TOPIC = "alerts";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createAlertsChannel();
        subscribeToAlerts();
    }

    /**
     * القناةُ يجبُ أن توجدَ باسمٍ مفهوم قبلَ وصولِ أوّلِ إشعار — وإلّا أنشأها
     * النظامُ بلا اسمٍ فرأى القارئُ في إعداداته قناةً مجهولةً لا يدري ما تُرسِل.
     * أهمّيّةٌ عالية: التحذيرُ الرسميُّ يستحقُّ الظهورَ فورًا، وهو وحدَه.
     */
    private void createAlertsChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm == null || nm.getNotificationChannel(CHANNEL_ID) != null) return;
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "التحذيراتُ الرسميّة", NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("تنبيهٌ عند صدورِ تحذيرٍ رسميٍّ مُسنَد — لا شيءَ سواه");
        nm.createNotificationChannel(ch);
    }

    /**
     * يُشترَكُ في موضوعِ التحذيراتِ إن كانت إعداداتُ Firebase موجودة.
     * بلا `google-services.json` تغيبُ الفئةُ كلُّها، فيُلتقَطُ الأمرُ صامتًا
     * ويبقى التطبيقُ عاملًا بالكامل — الإشعاراتُ وحدَها هي التي تنتظر.
     * (نفسُ نمطِ «المفتاحُ غائبٌ ⇒ تخطٍّ صامت» في الأنبوب.)
     */
    private void subscribeToAlerts() {
        try {
            Class<?> messaging = Class.forName("com.google.firebase.messaging.FirebaseMessaging");
            Object instance = messaging.getMethod("getInstance").invoke(null);
            messaging.getMethod("subscribeToTopic", String.class).invoke(instance, TOPIC);
        } catch (Throwable ignored) {
            // لا Firebase في هذه النسخة — التطبيقُ يعملُ، والإشعاراتُ معطّلة
        }
    }
}
