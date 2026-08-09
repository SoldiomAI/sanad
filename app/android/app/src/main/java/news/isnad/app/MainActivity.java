package news.isnad.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    /** قناةُ التحذيراتِ الرسميّة — القناةُ الوحيدة. لا قناةَ ترويجٍ ولا تذكير. */
    private static final String CHANNEL_ID = "sanad_alerts";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // الاشتراكُ في موضوعِ التحذيراتِ **لا يجري هنا**: يُنادى صراحةً من
        // `SanadPush.subscribe()` بعدَ موافقةِ القارئ. الاشتراكُ التلقائيُّ عند
        // الإقلاعِ كان يجعلُ كلَّ تثبيتٍ مشتركًا بلا استئذان — وعلى أندرويد ١٢
        // فأقدم لا إذنَ نظامٍ يمنعُ ذلك، فيصلُه الإشعارُ وهو لم يوافقْ قطّ.
        registerPlugin(SanadPush.class);
        super.onCreate(savedInstanceState);
        createAlertsChannel();
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
}
