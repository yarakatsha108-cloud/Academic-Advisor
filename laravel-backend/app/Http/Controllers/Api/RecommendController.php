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
    // ملاحظة على الرد (RecommendResponse) الراجع من بايثون: ما في struct
    // ثابت هون أصلاً - $response->json() بياخد أي شكل JSON كيفما كان،
    // وبينخزن/بيترجع كما هو. يعني أي حقل جديد تضيفوه لاحقاً بـ
    // RecommendResponse (متل total_avg وalso_eligible المضافين مؤخراً)
    // بيمر تلقائياً من دون أي تعديل هون - لا داعي تلمس هالملف كل ما
    // يتغيّر شكل رد بايثون.

    public function store(StoreSubmissionRequest $request)
    {
        $payload = $request->validated();

        // إذا لاحقاً صار عندكم فرق بأسماء حقول الفرونت إند عن أسماء
        // StudentRequest بـ api.py (متل مثال mark_math -> math_grade
        // المشروح بقسم 14 من دليل_بناء_الباك_اند_Laravel.md)، هون بالضبط
        // مكان إضافة خطوة التحويل - قبل ما نبعت $payload لبايثون.

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
