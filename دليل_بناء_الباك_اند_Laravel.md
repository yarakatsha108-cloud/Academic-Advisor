# دليل بناء الباك اند بـ Laravel (بوابة قدام خدمة Python الموجودة)

> **ملاحظة أمانة قبل ما تبلش:** بيئة التنفيذ عندي ما فيها PHP/Composer، فما قدرت أشغّل هالكود فعليًا بنفسي بالسيرفر. كتبته بعناية معتمدًا على توثيق Laravel الرسمي الحالي (تحققت منه لحظيًا - المشروع Laravel 12.x/13.x)، ورتبته كخطوات صغيرة، كل وحدة فيها معيار واضح "شلون تعرف إنها نجحت" قبل ما تكمل للي بعدها. هيك حتى لو في تفصيل بسيط يختلف بنسختك المحلية، بتعرف بالضبط وين وقفت المشكلة.

---

## 0. الصورة الكاملة قبل ما نبلش

```
Flutter  --(HTTP + Sanctum token)-->  Laravel  --(HTTP داخلي، بدون توكن)-->  Python (07_api.py)
                                          |                                        |
                                          v                                        v
                                   قاعدة بيانات Laravel                    نفس المنطق الحالي
                                (users, submissions)                    (06_recommend.py بدون تغيير)
```

Laravel هو الشي الوحيد اللي Flutter بيحكي معه. خدمة بايثون تضل شغالة محليًا (`127.0.0.1:8000`)، وLaravel هو اللي بيوصلها من الداخل. ما رح نلمس ولا سطر من `06_recommend.py` أو `07_api.py`.

---

## 1. المتطلبات قبل ما تبلش

| الأداة | ليش لازمة | كيف تتأكد إنها مركّبة |
|---|---|---|
| PHP 8.2 أو أحدث | Laravel 12/13 محتاجها | `php -v` |
| Composer | يركّب مكتبات Laravel | `composer -V` |
| SQLite (مدمج بـ PHP عادةً) | قاعدة بيانات بسيطة، صفر إعداد سيرفر | ما محتاج تركيب منفصل غالبًا |
| Postman أو curl | لتجربة كل endpoint يدويًا | أي وحدة فيهم تكفي |
| خدمة بايثون (07_api.py) شغّالة | Laravel رح يتصل فيها | `uvicorn 07_api:app --port 8000` بترمينال منفصل |

لو `php -v` ما اشتغل، لازم تركّب PHP أول (على ويندوز أسهل طريقة عبر [Laravel Herd](https://herd.laravel.com) - بيجيب PHP وComposer سوا بتثبيت واحد).

---

## 2. خطوة 1 - إنشاء المشروع

```bash
composer create-project laravel/laravel recommendation-backend
cd recommendation-backend
php artisan serve
```

**معيار النجاح:** تفتح `http://127.0.0.1:8000` بالمتصفح وتشوف صفحة Laravel الافتراضية (خلفية زرقاء فاتحة، شعار Laravel). لو شفت هيك، المشروع شغّال وقاعد نبني عليه.

أوقف السيرفر (`Ctrl+C`) قبل ما تكمل، رح ترجعله لاحقًا.

---

## 3. خطوة 2 - قاعدة البيانات (SQLite)

بملف `.env` بجذر المشروع، دوّر على هالأسطر وعدّلهم:

```env
DB_CONNECTION=sqlite
# احذف أو علّق (#) أسطر DB_HOST, DB_PORT, DB_DATABASE, DB_USERNAME, DB_PASSWORD
```

بعدين أنشئ ملف قاعدة البيانات الفعلي:

```bash
# على ماك/لينكس:
touch database/database.sqlite
# على ويندوز (PowerShell):
New-Item database/database.sqlite -ItemType File
```

وشغّل أول migration (Laravel جاهز بيه جدول users افتراضيًا):

```bash
php artisan migrate
```

**معيار النجاح:** بتشوف بالترمينال أسماء migrations وجنبها `DONE` (مثل `create_users_table ... DONE`). لو صار خطأ "could not find driver"، معناته PHP مش مركّب معه SQLite extension - راجع تثبيت PHP.

---

## 4. خطوة 3 - تركيب Sanctum (نظام تسجيل الدخول بالتوكن)

Laravel 12/13 عندها أمر واحد بيعمل كل شي:

```bash
php artisan install:api
```

هالأمر بيعمل تلقائيًا:
- يركّب حزمة `laravel/sanctum` عبر Composer.
- ينشئ `routes/api.php` (لو مش موجود أصلًا - بمشروع Laravel جديد عادةً مش موجود).
- يضيف migration جدول `personal_access_tokens` (جدول التوكنات).
- يضيف middleware الـ API تلقائيًا.

بعدين شغّل الـ migration الجديدة:

```bash
php artisan migrate
```

**تحقّق مهم:** افتح `app/Models/User.php` وتأكد إنو فيه هالسطر (لو الأمر ما ضافه تلقائيًا، ضيفه يدويًا):

```php
use Laravel\Sanctum\HasApiTokens;

class User extends Authenticatable
{
    use HasApiTokens, HasFactory, Notifiable;
    // ...
}
```

**معيار النجاح:** شغّل `php artisan route:list` وتأكد إنك شايف مسارات جديدة تبدأ بـ `api/` (حتى لو لسا فاضية غير الافتراضي).

---

## 5. خطوة 4 - جدول submissions (حفظ كل تعبئة استبيان)

أنشئ migration جديدة:

```bash
php artisan make:migration create_submissions_table
```

بيفتح لك ملف بمجلد `database/migrations/xxxx_create_submissions_table.php` - افتحه واستبدل محتواه بهاد بالضبط:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('submissions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->json('student_answers');
            $table->json('recommendation_result');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('submissions');
    }
};
```

**شرح كل سطر:**
- `foreignId('user_id')->constrained()` - يربط كل submission بمستخدم موجود فعليًا بجدول users، وبيتأكد Laravel من هالربط تلقائيًا.
- `cascadeOnDelete()` - لو انحذف المستخدم يومًا، تنحذف submissions تبعه معه تلقائيًا (بدل ما تضل يتيمة بقاعدة البيانات).
- `json('student_answers')` و `json('recommendation_result')` - نخزّن الطلب الأصلي والرد الكامل كـ JSON خام، بدل ما نصمم عمود منفصل لكل حقل من الـ25 حقل - أبسط بكثير وكافي تمامًا لهالحالة.

شغّل الـ migration:

```bash
php artisan migrate
```

**معيار النجاح:** `create_submissions_table ... DONE` بالترمينال.

---

## 6. خطوة 5 - الموديل (Submission)

```bash
php artisan make:model Submission
```

افتح `app/Models/Submission.php` واستبدله بـ:

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Submission extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id',
        'student_answers',
        'recommendation_result',
    ];

    protected function casts(): array
    {
        return [
            'student_answers' => 'array',
            'recommendation_result' => 'array',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
```

**شرح `casts()`:** بدون هالسطر، Eloquent بيرجّعلك عمود `student_answers` كنص JSON خام (string). مع `'array'`، Laravel بيحوّله تلقائيًا لـ PHP array وقت القراءة، وبيحوّله تلقائيًا لـ JSON وقت الحفظ - ما محتاج `json_encode`/`json_decode` يدويًا بأي مكان بالكود.

وبملف `app/Models/User.php`، ضيف هالعلاقة العكسية (جوا الكلاس، بعد استخدام الـ traits):

```php
public function submissions(): \Illuminate\Database\Eloquent\Relations\HasMany
{
    return $this->hasMany(Submission::class);
}
```

---

## 7. خطوة 6 - تسجيل الدخول (AuthController)

```bash
php artisan make:controller Api/AuthController
```

افتح `app/Http/Controllers/Api/AuthController.php` واستبدله بـ:

```php
<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\ValidationException;

class AuthController extends Controller
{
    public function register(Request $request)
    {
        $validator = Validator::make($request->all(), [
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'string', 'email', 'max:255', 'unique:users,email'],
            'password' => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        if ($validator->fails()) {
            return response()->json(['errors' => $validator->errors()], 422);
        }

        $user = User::create([
            'name' => $request->name,
            'email' => $request->email,
            'password' => Hash::make($request->password),
        ]);

        $token = $user->createToken('flutter-app')->plainTextToken;

        return response()->json([
            'user' => $user,
            'access_token' => $token,
            'token_type' => 'Bearer',
        ], 201);
    }

    public function login(Request $request)
    {
        $request->validate([
            'email' => ['required', 'email'],
            'password' => ['required'],
        ]);

        $user = User::where('email', $request->email)->first();

        if (! $user || ! Hash::check($request->password, $user->password)) {
            throw ValidationException::withMessages([
                'email' => ['بيانات الدخول غير صحيحة.'],
            ]);
        }

        $token = $user->createToken('flutter-app')->plainTextToken;

        return response()->json([
            'user' => $user,
            'access_token' => $token,
            'token_type' => 'Bearer',
        ]);
    }

    public function logout(Request $request)
    {
        $request->user()->currentAccessToken()->delete();

        return response()->json(['message' => 'تم تسجيل الخروج.']);
    }

    public function me(Request $request)
    {
        return response()->json($request->user());
    }
}
```

**شرح النقاط المهمة:**
- `Hash::make()` / `Hash::check()` - Laravel بيستخدم bcrypt تلقائيًا (مدمج، ما محتاج تركيب أي مكتبة إضافية). كلمة السر أبدًا ما تُخزَّن كنص صريح.
- `'password' => ['required', 'string', 'min:8', 'confirmed']` - كلمة `confirmed` معناها Laravel بيتوقع حقل إضافي اسمه `password_confirmation` بنفس الطلب، ويتأكد إنو مطابق - حماية من غلطة كتابة كلمة السر.
- `createToken('flutter-app')` - الاسم "flutter-app" هون بس تسمية وصفية للتوكن (متل "من وين انبعت"), ما إلها تأثير وظيفي.
- `$user->createToken(...)->plainTextToken` - هاي القيمة اللي لازم Flutter يخزّنها (بـ `flutter_secure_storage` مثلاً) ويرسلها بـ header `Authorization: Bearer <القيمة>` مع كل طلب بعدها.

---

## 8. خطوة 7 - التحقق من إجابات الطالب (Form Request)

هاي الخطوة الأهم عشان Laravel يرفض أي بيانات ناقصة أو غلط **قبل** ما يبعتها لخدمة بايثون - يوفر عليك أخطاء غامضة من جهة بايثون.

```bash
php artisan make:request StoreSubmissionRequest
```

افتح `app/Http/Requests/StoreSubmissionRequest.php` واستبدله بـ:

```php
<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreSubmissionRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // الحماية الفعلية بـ auth:sanctum middleware على المسار نفسه
    }

    public function rules(): array
    {
        return [
            'academic_branch' => ['required', 'integer', 'in:1,2,4,5'],

            // 20 ميزة التجميع (Likert 1-5 أو 1-4 أو علامات 0-100)
            'interest_math' => ['required', 'integer', 'between:1,5'],
            'interest_physics_engineering' => ['required', 'integer', 'between:1,5'],
            'interest_medicine' => ['required', 'integer', 'between:1,5'],
            'interest_chemistry_biology' => ['required', 'integer', 'between:1,5'],
            'interest_humanities' => ['required', 'integer', 'between:1,5'],
            'interest_economics' => ['required', 'integer', 'between:1,5'],
            'interest_arts' => ['required', 'integer', 'between:1,5'],
            'interest_law' => ['required', 'integer', 'between:1,5'],
            'prefer_theoretical' => ['required', 'integer', 'between:1,5'],
            'enjoy_complex_problems' => ['required', 'integer', 'between:1,5'],
            'handle_academic_pressure' => ['required', 'integer', 'between:1,5'],
            'priority_income' => ['required', 'integer', 'between:1,4'],
            'priority_social_status' => ['required', 'integer', 'between:1,4'],
            'priority_passion' => ['required', 'integer', 'between:1,4'],
            'priority_job_stability' => ['required', 'integer', 'between:1,4'],
            'math_grade' => ['required', 'numeric', 'between:0,100'],
            'physics_grade' => ['required', 'numeric', 'between:0,100'],
            'chemistry_grade' => ['required', 'numeric', 'between:0,100'],
            'arabic_grade' => ['required', 'numeric', 'between:0,100'],
            'foreign_language_grade' => ['required', 'numeric', 'between:0,100'],

            // 5 إشارات (signals) منقولة لمحرك التوصية
            'interest_programming' => ['required', 'integer', 'between:1,5'],
            'interest_languages' => ['required', 'integer', 'between:1,5'],
            'prefer_people_over_computer' => ['required', 'integer', 'between:1,5'],
            'can_study_outside_city' => ['required', 'integer', 'between:0,1'],
            'can_study_private_university_encoded' => ['required', 'numeric', 'in:0,0.5,1'],

            'exam_stage' => ['sometimes', 'string', 'in:mid_year,supplementary_round_available,final'],
        ];
    }
}
```

**ملاحظة حرجة جدًا:** أسماء الحقول هون (`interest_math`, `math_grade`, إلخ) هي **بالضبط** نفس أسماء `StudentRequest` بملف `07_api.py` عندك - نسختها منه حرفيًا. **لا تغيّر ولا اسم حقل واحد هون** حتى لو حابب تسميه شي تاني - أي فرق بالاسم رح يخلي خدمة بايثون ترفض الطلب بخطأ 422 مو مفهوم السبب. لو ضفتوا لاحقًا حقل جديد بـ 07_api.py، لازم تضيفوه هون كمان بنفس الاسم بالضبط.

---

## 9. خطوة 8 - RecommendController (قلب الربط بين Laravel وبايثون)

بملف `.env`، ضيف بالآخر:

```env
RECOMMEND_SERVICE_URL=http://127.0.0.1:8000
```

وبملف `config/services.php`، جوا الـ array الرئيسي، ضيف:

```php
'recommend' => [
    'url' => env('RECOMMEND_SERVICE_URL', 'http://127.0.0.1:8000'),
],
```

**ليش هالخطوة الإضافية؟** بدل ما تقرأ `env('RECOMMEND_SERVICE_URL')` مباشرة جوا الكنترولر، الطريقة الصحيحة بـ Laravel هي قراءتها عبر `config('services.recommend.url')`. السبب: Laravel بيكاش (cache) ملفات الـ config بالإنتاج لأداء أسرع، وقراءة `env()` مباشرة برا ملفات config بتنكسر بعد الكاش. عادة تافهة بس بتوفرلك صداع كبير لاحقًا.

الآن الكنترولر:

```bash
php artisan make:controller Api/RecommendController
```

```php
<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreSubmissionRequest;
use App\Models\Submission;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class RecommendController extends Controller
{
    public function store(StoreSubmissionRequest $request)
    {
        $payload = $request->validated();

        try {
            $response = Http::timeout(10)
                ->acceptJson()
                ->post(config('services.recommend.url') . '/recommend', $payload);
        } catch (\Illuminate\Http\Client\ConnectionException $e) {
            Log::error('Python recommend service unreachable: ' . $e->getMessage());

            return response()->json([
                'message' => 'خدمة التوصية غير متاحة حاليًا، حاول لاحقًا.',
            ], 503);
        }

        if ($response->failed()) {
            Log::error('Python recommend service returned an error', [
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            return response()->json([
                'message' => 'حدث خطأ أثناء حساب التوصية.',
                'details' => $response->json(),
            ], 502);
        }

        $result = $response->json();

        $submission = Submission::create([
            'user_id' => $request->user()->id,
            'student_answers' => $payload,
            'recommendation_result' => $result,
        ]);

        return response()->json([
            'submission_id' => $submission->id,
            'recommendation' => $result,
        ], 201);
    }

    public function history(Request $request)
    {
        $submissions = $request->user()
            ->submissions()
            ->latest()
            ->paginate(10);

        return response()->json($submissions);
    }
}
```

**شرح القرارات هون:**
- `Http::timeout(10)` - لو خدمة بايثون علقت أو بطيئة جدًا، ما رح يعلّق طلب Flutter لأكتر من 10 ثواني - بيرجع خطأ واضح بدل ما يفضل معلّق للأبد.
- `try/catch` على `ConnectionException` تحديدًا - هاي الحالة اللي بتصير لو خدمة بايثون مش شغّالة أصلًا (مثلاً نسيت تشغّل uvicorn). بترجع 503 (Service Unavailable) بدل ما التطبيق يطيح بخطأ 500 غامض.
- `$response->failed()` - يغطي حالة تانية: خدمة بايثون شغّالة، بس رجعت خطأ (مثلاً validation error من Pydantic لو في حقل ناقص رغم كل التحقق اللي عملناه بـ Laravel - طبقة حماية إضافية).
- **مهم:** الحفظ بقاعدة البيانات (`Submission::create`) يصير **بعد** ما نتأكد الرد نجح، مو قبل - هيك ما بنخزن submissions فاشلة بدون نتيجة حقيقية.
- `Log::error(...)` - بيسجل التفاصيل بملف `storage/logs/laravel.log` بدون ما يكشفها للمستخدم النهائي (فرق مهم بين "شو نعرضه للطالب" و"شو نسجله لأنفسنا للتصحيح لاحقًا").

---

## 10. خطوة 9 - الـ Routes (تجميع كل شي)

افتح `routes/api.php` واستبدل محتواه بـ:

```php
<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\RecommendController;
use Illuminate\Support\Facades\Route;

Route::post('/auth/register', [AuthController::class, 'register']);
Route::post('/auth/login', [AuthController::class, 'login']);

Route::middleware('auth:sanctum')->group(function () {
    Route::post('/auth/logout', [AuthController::class, 'logout']);
    Route::get('/auth/me', [AuthController::class, 'me']);

    Route::post('/recommend', [RecommendController::class, 'store']);
    Route::get('/recommend/history', [RecommendController::class, 'history']);
});
```

**شرح `Route::middleware('auth:sanctum')->group(...)`:** كل مسار جوا هالـ group محمي - لازم يجي معه header صحيح `Authorization: Bearer <token>`، وإلا Laravel يرجّع 401 تلقائيًا قبل ما يوصل الكود جوا الكنترولر أصلًا. مسارات التسجيل/الدخول لوحدها برا الـ group لأنو المستخدم لسا ما عنده توكن أصلًا وقتها.

---

## 11. خطوة 10 - التشغيل والاختبار الفعلي، خطوة خطوة

افتح **ترمينالين منفصلين**:

**ترمينال 1 (خدمة بايثون - من مجلد المشروع الأصلي):**
```bash
uvicorn 07_api:app --reload --port 8000
```

**ترمينال 2 (Laravel - من مجلد recommendation-backend):**
```bash
php artisan serve
```

الآن جرّب بالترتيب (عبر curl أو Postman):

**1) تسجيل حساب جديد:**
```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"طالب تجريبي","email":"test@example.com","password":"password123","password_confirmation":"password123"}'
```
> انتبه: هون `127.0.0.1:8000` هو منفذ **Laravel** (`php artisan serve` بيشتغل افتراضيًا على 8000 أيضًا - لو خدمة بايثون آخذاه، شغّل Laravel على منفذ تاني بـ `php artisan serve --port=8001`).

**المتوقع:** رد 201 فيه `access_token`. **انسخ هالتوكن** - رح تحتاجه بالخطوة الجاية.

**2) تجربة /auth/me بالتوكن:**
```bash
curl http://127.0.0.1:8001/api/auth/me \
  -H "Authorization: Bearer <التوكن_يلي_نسخته>"
```
**المتوقع:** بيانات المستخدم (الاسم، الإيميل). لو رجع 401، التوكن غلط أو ناقص.

**3) إرسال توصية:**
```bash
curl -X POST http://127.0.0.1:8001/api/recommend \
  -H "Authorization: Bearer <التوكن>" \
  -H "Content-Type: application/json" \
  -d '{
    "academic_branch": 1, "interest_math": 5, "interest_physics_engineering": 5,
    "interest_medicine": 5, "interest_chemistry_biology": 4, "interest_humanities": 2,
    "interest_economics": 2, "interest_arts": 1, "interest_law": 2,
    "prefer_theoretical": 3, "enjoy_complex_problems": 5, "handle_academic_pressure": 5,
    "priority_income": 2, "priority_social_status": 3, "priority_passion": 1, "priority_job_stability": 4,
    "math_grade": 92, "physics_grade": 90, "chemistry_grade": 88,
    "arabic_grade": 80, "foreign_language_grade": 85,
    "interest_programming": 3, "interest_languages": 3, "prefer_people_over_computer": 5,
    "can_study_outside_city": 1, "can_study_private_university_encoded": 1,
    "exam_stage": "mid_year"
  }'
```
**المتوقع:** رد 201 فيه `submission_id` وكائن `recommendation` كامل (نفس شكل رد `/recommend` تبع بايثون بالضبط).

**4) تجربة السجل:**
```bash
curl http://127.0.0.1:8001/api/recommend/history \
  -H "Authorization: Bearer <التوكن>"
```
**المتوقع:** قائمة فيها الـ submission اللي عملته لتوّك.

لو الأربع خطوات هدول نجحوا بالترتيب، الباك اند كامل شغّال وجاهز يوصله Flutter.

---

## 12. مشاكل متوقعة وحلولها

| العرض | السبب الأغلب | الحل |
|---|---|---|
| 503 من `/api/recommend` | خدمة بايثون مش شغّالة، أو المنفذ غلط | تأكد `uvicorn` شغّال، وتأكد `RECOMMEND_SERVICE_URL` بـ `.env` مطابق للمنفذ الصح |
| 422 عند التسجيل | كلمة سر أقل من 8 أحرف، أو `password_confirmation` ناقصة، أو إيميل مستخدم مسبقًا | اقرأ حقل `errors` بالرد، بيحدد المشكلة بالضبط |
| 401 على أي مسار محمي | التوكن ناقص، منتهي، أو الصيغة غلط | تأكد الـ header بالضبط `Authorization: Bearer <token>` (مسافة وحدة بعد Bearer) |
| 502 من `/api/recommend` | بايثون رجّع خطأ فعليًا (مثلاً حقل خارج المدى) | شوف `details` بالرد - غالبًا رح يكون رسالة Pydantic واضحة |
| "could not find driver" وقت migrate | PHP بدون SQLite extension | تأكد `php -m \| grep sqlite` يطلع نتيجة، وإلا ركّب/فعّل الـ extension |
| كل شي شغّال محليًا بس Flutter عالموبايل الحقيقي ما بيوصل | `127.0.0.1` بمعنى "نفس الجهاز فقط" - موبايل حقيقي (مش محاكي) ما بيقدر يوصلها | استخدم IP الشبكة المحلية لجهازك (مثلاً `192.168.1.x`) بدل `127.0.0.1` بإعدادات Flutter، وتأكد الجدار الناري مسموح |

---

## 13. ملحق: البرومبت الكامل (لو حبيت تدّي المهمة لأداة تانية بدل التنفيذ اليدوي)

كل الكود بالأقسام فوق جاهز للنسخ المباشر - ما محتاج برومبت إذا رح تنفّذ بنفسك. بس لو حابب تفوّض التنفيذ لـ Claude Code أو مطوّر تاني بالتيم، هاد البرومبت الكامل يغطي كل التفاصيل:

```
المطلوب: باك اند Laravel كامل يشتغل كـ "بوابة" (gateway) قدام خدمة Python موجودة
مسبقًا وشغّالة ومختبرة (FastAPI على 07_api.py) - بدون أي تعديل على خدمة Python.

السياق:
- عندي خدمة Python (FastAPI) شغّالة محليًا على http://127.0.0.1:8000، فيها نقطة
  POST /recommend بتاخد JSON فيه إجابات طالب على استبيان (شوف الملف المرفق
  07_api.py لمعرفة الحقول بالضبط: StudentRequest و RecommendResponse) وترجع
  توصية تخصص جامعي كاملة.
- الفرونت إند Flutter، وفيه واجهة تسجيل دخول + واجهة تعبئة استبيان جاهزتين
  عند التيم، بيحتاجوا Laravel API حقيقي يتواصلوا معه.
- هالخدمة الـ Python ما لازم تُعدَّل ولا تُعرَّض للإنترنت مباشرة - Laravel وحده
  اللي بيكلّمها.

المطلوب إضافته بالضبط:

1. مصادقة عبر Laravel Sanctum (مناسب لتطبيق موبايل، توكن بسيط لا OAuth كامل):
   - POST /api/auth/register  {name, email, password, password_confirmation}
     -> ينشئ حساب، يرجّع access_token
   - POST /api/auth/login     {email, password}
     -> يتحقق، يرجّع access_token
   - POST /api/auth/logout    (محمي بالتوكن) -> يلغي التوكن الحالي
   - GET  /api/auth/me        (محمي بالتوكن) -> بيانات المستخدم الحالي

2. Migration وModel لجدول submissions:
   - id, user_id (foreign key على users)، student_answers (json)،
     recommendation_result (json)، created_at
   - Model: Submission، مع علاقة belongsTo(User) وعلاقة عكسية على User.

3. RecommendController (محمي بـ Sanctum middleware):
   - POST /api/recommend:
     a. تحقق (Form Request validation) من كل حقول StudentRequest كما هي بالضبط
        بـ 07_api.py (نفس الأسماء، نفس القيود ge/le) - لا تُعِد تسمية أي حقل.
     b. أرسل نفس الـ payload عبر Http::post() لـ
        config('services.recommend.url') . '/recommend' (اقرأ الرابط من .env
        عبر config/services.php، لا تكتبه ثابتًا بالكود).
     c. لو الخدمة رجّعت خطأ أو ما ردّت (timeout)، رجّع خطأ واضح للفرونت إند
        (503 مثلاً) بدل ما يفشل بصمت.
     d. لو نجحت، احفظ صف بـ submissions (user_id من auth()->id()،
        student_answers = الطلب الأصلي، recommendation_result = الرد)
        وبعدين رجّع نفس رد بايثون كما هو للفرونت إند.
   - GET /api/recommend/history (محمي): كل submissions المستخدم الحالي،
     الأحدث أولاً، مع pagination بسيطة (paginate(10) مثلاً).

4. إعدادات:
   - أضف RECOMMEND_SERVICE_URL=http://127.0.0.1:8000 لملف .env و.env.example.
   - اضبط timeout معقول (5-10 ثواني) لطلبات Http:: الداخلية.

5. لا تلمس أبدًا:
   - أي ملف Python (06_recommend.py، 07_api.py، أو نماذج .pkl).
   - أسماء حقول StudentRequest/RecommendResponse - Laravel ناقل وحافظ بيانات
     فقط، مو طبقة إعادة صياغة.

6. بعد التنفيذ، اكتب لي:
   - أوامر artisan اللازمة (migrate، إلخ).
   - أمثلة curl لكل نقطة API جديدة.
   - كيف يشغّل Laravel وPython سوا محليًا وقت التطوير (أمرين منفصلين، أو
     ملاحظة إذا لازم Procfile/supervisor).
```

> **ملاحظة صغيرة:** عدّلت سطر واحد بالبرومبت عن نسخته الأصلية اللي انكتبت بالمحادثة (استبدلت `env('RECOMMEND_SERVICE_URL')` بـ `config('services.recommend.url')`) عشان يبقى متسق مع شرح القسم 9 فوق - نفس الفكرة بالضبط، بس الطريقة الصح لقراءة إعدادات بـ Laravel.

---

## 14. ملحق 2 - تحويل حقول الفرونت إند (39 حقل) لحقول خدمة الذكاء الاصطناعي (27 حقل)

الفرونت إند (Flutter) بيبعت 39 حقل بأسماء خاصة فيه (مثلاً `mark_math`)، بينما خدمة بايثون بتتوقع 27 حقل بأسماء مختلفة (`math_grade`). القرار: **Laravel هو اللي بيترجم**، الفرونت إند ما بيتغيّر.

الحل: array تحويل واحد، مكانه الطبيعي جوا `RecommendController`، قبل ما نبعت أي شي لخدمة بايثون.

```php
// أضف بأعلى RecommendController.php (بعد namespace/use statements)

/**
 * تحويل من أسماء حقول الفرونت إند (39 حقل) لأسماء StudentRequest
 * بخدمة بايثون (27 حقل بالضبط). المفتاح = اسم الفرونت إند،
 * القيمة = الاسم المتوقع بـ api.py.
 *
 * عدّل القيم اليسار (الفرونت إند) لتطابق أسماءكم الفعلية - القيم
 * اليمين (خدمة بايثون) ثابتة، منسوخة حرفيًا من StudentRequest.
 */
private const FIELD_MAP = [
    'mark_math' => 'math_grade',
    'mark_physics' => 'physics_grade',
    'mark_chemistry' => 'chemistry_grade',
    'mark_arabic' => 'arabic_grade',
    'mark_foreign_language' => 'foreign_language_grade',
    // ... باقي الـ22 حقل، بنفس النمط: 'اسم_الفرونت' => 'اسم_بايثون'
    // (القائمة الكاملة الـ27 موجودة بقسم 8 فوق - StoreSubmissionRequest)
];
```

وبدالة `store()`، قبل التحقق (validation)، حوّل الطلب الوارد أول:

```php
public function store(Request $request)
{
    // 1) حوّل أسماء الحقول من صيغة الفرونت إند لصيغة خدمة بايثون
    $mapped = [];
    foreach (self::FIELD_MAP as $frontendKey => $pythonKey) {
        if ($request->has($frontendKey)) {
            $mapped[$pythonKey] = $request->input($frontendKey);
        }
    }

    // 2) الآن مرّر $mapped (مو $request->all()) لـ StoreSubmissionRequest
    //    للتحقق - نفس القواعد المكتوبة بقسم 8 بالضبط، بدون أي تغيير عليها
    $validator = \Validator::make($mapped, (new StoreSubmissionRequest())->rules());

    if ($validator->fails()) {
        return response()->json(['errors' => $validator->errors()], 422);
    }

    $payload = $validator->validated();

    // 3) من هون وطالع، نفس كود القسم 9 بالضبط (Http::post مع $payload)
    // ...
}
```

**نقاط مهمة:**
- أي حقل من الـ39 مش موجود بـ `FIELD_MAP` (يعني من الـ12 الزيادة) **ببساطة بينرمى ولا بيوصل لخدمة بايثون** - مو خطأ، هيك المفروض بالضبط.
- لو حابين تحتفظوا بالـ39 حقل الأصلية كاملة بقاعدة البيانات (submissions) لغرض تاني بالمستقبل، خزّنوا `$request->all()` بعمود `student_answers` بدل `$mapped` - القرار إلكم، ما بأثر على أي شي عملي.
- لو تغيّر اسم حقل بأي طرف (فرونت إند أو بايثون) بالمستقبل، المكان الوحيد اللي لازم تعدّلوه هو `FIELD_MAP` - كل شي تاني بالكود ما بيتغيّر.
