<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

// !! أسماء الحقول هون طابقتها حرفياً مع StudentRequest بملف api.py الحالي
// (آخر نسخة، بعد إضافة total_avg/also_eligible بالرد - هاي الحقول هون
// كلها حقول *الطلب* مو الرد، فما تغيّرت). لا تغيّر ولا اسم حقل واحد -
// أي فرق بالاسم رح يخلي خدمة بايثون ترفض الطلب بخطأ 422.
//
// ملاحظة: academic_branch هون مقيّد بـ in:1,2,4,5 (بدون 3) - هيك كان
// بالدليل الأصلي، رغم إنو BRANCH_NAMES بـ recommend.py فيها 3="Commercial"
// كمان. إذا الاستبيان/الفرونت إند فعلياً بيجمع فرع "تجاري" (3)، لازم تضيفوه
// هون يدوياً - ما بدلتها بنفسي لأني مش متأكد هل هالفرع مطروح فعلياً
// بالاستبيان أو استُبعد قصداً.

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

            // 5 إشارات (signals) منقولة لمحرك التوصية كباراميترات منفصلة
            // (مو ضمن student_answers) - راجع docstring recommend.py
            'interest_programming' => ['required', 'integer', 'between:1,5'],
            'interest_languages' => ['required', 'integer', 'between:1,5'],
            'prefer_people_over_computer' => ['required', 'integer', 'between:1,5'],
            'can_study_outside_city' => ['required', 'integer', 'between:0,1'],
            'can_study_private_university_encoded' => ['required', 'numeric', 'in:0,0.5,1'],

            'exam_stage' => ['sometimes', 'string', 'in:mid_year,supplementary_round_available,final'],
        ];
    }
}
