<?php

// هاد مو ملف كامل - هاد بس القطعة يلي لازم تضيفوها جوا الـ array
// الرئيسي بملف config/services.php الموجود عندكم أصلاً (فيه postmark/ses/
// resend افتراضياً - لا تستبدلوا الملف كامل، بس ضيفوا هالسطر جواه):

'recommend' => [
    'url' => env('RECOMMEND_SERVICE_URL', 'http://127.0.0.1:8000'),
],
