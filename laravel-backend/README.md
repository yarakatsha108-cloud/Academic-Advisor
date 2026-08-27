# ملفات الباك اند الجاهزة - كيف تستخدمها

هاد المجلد فيه الملفات **الفعلية** يلي لازم تنسخيها جوا مشروع Laravel جديد -
مو نص بشرحلك تنسخو يدوياً متل الدليل الأصلي (`دليل_بناء_الباك_اند_Laravel.md`
بجذر المشروع، لسا موجود ولسا صالح لو احتجتي تفاصيل/استكشاف أخطاء أعمق).

**ليش هيك بدل ما شغّلها إلك مباشرة؟** بيئتي هون ما فيها PHP/Composer (جربت
أركبهم، ما نجح) - فما فيني أشغّل `composer create-project` ولا أختبر الكود
فعلياً. الملفات هون مكتوبة بعناية ومطابقة لدليل الإعداد + لأسماء حقول
`api.py` الحالية بالضبط، بس التشغيل والاختبار الفعلي لازم يصير عندك.

## خطوات الاستخدام

1. أنشئ مشروع Laravel جديد (إذا لسا ما عملتيه):
   ```bash
   composer create-project laravel/laravel recommendation-backend
   cd recommendation-backend
   php artisan install:api
   ```

2. انسخي كل ملف من هالمجلد لنفس المسار **بالضبط** جوا مشروعك (استبدال كامل
   لكل ملف، ما عدا الاثنين المذكورين بالخطوة 3):
   ```
   database/migrations/2024_01_01_000001_create_submissions_table.php
   app/Models/Submission.php
   app/Models/User.php                          <- استبدال كامل
   app/Http/Controllers/Api/AuthController.php
   app/Http/Controllers/Api/RecommendController.php
   app/Http/Requests/StoreSubmissionRequest.php
   routes/api.php                                <- استبدال كامل
   ```

3. الاثنين هدول **مو استبدال كامل** - ضيفي القطعة بس جوا الملف الموجود
   عندك أصلاً:
   - `.env`: ضيفي بالآخر:
     ```env
     RECOMMEND_SERVICE_URL=http://127.0.0.1:8000
     ```
   - `config/services.php`: افتحي `laravel-backend/config/services.snippet.php`
     هون وضيفي محتواه جوا الـ array الرئيسي بملف `config/services.php`
     الحقيقي عندك (ما تستبدليه كامل - فيه postmark/ses/resend افتراضياً).

4. شغّلي المايجريشن:
   ```bash
   php artisan migrate
   ```
   **معيار النجاح:** `create_submissions_table ... DONE` بالترمينال.

5. جربي - نفس أوامر curl الموجودة بقسم 11 من `دليل_بناء_الباك_اند_Laravel.md`
   (تسجيل حساب -> auth/me -> POST /api/recommend -> GET /api/recommend/history).

## لو صار خطأ

راجعي جدول "مشاكل متوقعة وحلولها" بقسم 12 من `دليل_بناء_الباك_اند_Laravel.md` -
لسا صالح بالكامل، ما تغيّر منو شي.

## ملاحظة مهمة واحدة

`academic_branch` بـ `StoreSubmissionRequest.php` مقيّد بـ `in:1,2,4,5`
(بدون 3="تجاري"). هيك كان بالدليل الأصلي من البداية - ما بدلتها بنفسي لأني
مش متأكدة/متأكد هل فرع "تجاري" فعلاً مطروح بالاستبيان أو مستبعد قصداً. إذا
لازم يتضاف، عدّلي السطر لـ `in:1,2,3,4,5` بس.
