<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

// اسم الملف لازم يبلش بتاريخ (timestamp) أقدم من ملف create_personal_access_tokens_table
// يلي بينعمل تلقائياً من "php artisan install:api" - إذا حابب تولّده بنفسك بدل نسخ هالاسم
// جاهز، استخدم: php artisan make:migration create_submissions_table
// وبعدين استبدل محتوى الملف الجديد بمحتوى هالملف بالضبط (بدون تغيير اسم الملف).

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
