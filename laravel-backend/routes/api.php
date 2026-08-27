<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\RecommendController;
use Illuminate\Support\Facades\Route;

// هاد الملف عادة مش موجود بمشروع Laravel جديد إلا بعد ما تشغّلوا
// "php artisan install:api" (يلي بينشئه فاضي تقريباً). استبدلوا محتواه
// بهالمحتوى بالكامل.

Route::post('/auth/register', [AuthController::class, 'register']);
Route::post('/auth/login', [AuthController::class, 'login']);

Route::middleware('auth:sanctum')->group(function () {
    Route::post('/auth/logout', [AuthController::class, 'logout']);
    Route::get('/auth/me', [AuthController::class, 'me']);

    Route::post('/recommend', [RecommendController::class, 'store']);
    Route::get('/recommend/history', [RecommendController::class, 'history']);
});
