<?php

namespace App\Models;

// use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Laravel\Sanctum\HasApiTokens;

// هاد الملف نسخة كاملة بديلة عن app/Models/User.php الافتراضي يلي Laravel
// بينشئه تلقائياً - انسخو فوق الملف الموجود عندك بالكامل (بعد ما تشغّل
// "php artisan install:api"، يلي بيضيف HasApiTokens تلقائياً غالباً، بس
// هاد الملف بيضمنها موجودة + علاقة submissions() جاهزة).

class User extends Authenticatable
{
    /** @use HasFactory<\Database\Factories\UserFactory> */
    use HasApiTokens, HasFactory, Notifiable;

    protected $fillable = [
        'name',
        'email',
        'password',
    ];

    protected $hidden = [
        'password',
        'remember_token',
    ];

    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
        ];
    }

    public function submissions(): HasMany
    {
        return $this->hasMany(Submission::class);
    }
}
