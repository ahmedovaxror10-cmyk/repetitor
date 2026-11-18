import functools
import os
import re
import secrets
import shutil
import sqlite3
import time
import uuid
from flask import Flask, request, redirect, render_template, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_VERSION = "20261118-v4"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "faqat-sinov-uchun-kalit-2026-repetitor")
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("PRODUCTION") == "1"

if os.environ.get("VERCEL"):
    DB = "/tmp/repetitor.db"
    src_db = os.path.join(BASE, "repetitor.db")
    if os.path.exists(src_db) and not os.path.exists(DB):
        try:
            shutil.copy2(src_db, DB)
        except Exception as e:
            print("DB copy error:", e)

    UPLOAD = "/tmp/uploads"
    os.makedirs(UPLOAD, exist_ok=True)
    src_uploads = os.path.join(BASE, "static", "uploads")
    if os.path.exists(src_uploads):
        for f in os.listdir(src_uploads):
            src_f = os.path.join(src_uploads, f)
            dst_f = os.path.join(UPLOAD, f)
            if os.path.isfile(src_f) and not os.path.exists(dst_f):
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass
else:
    DB = os.path.join(BASE, "repetitor.db")
    UPLOAD = os.path.join(BASE, "static", "uploads")
    os.makedirs(UPLOAD, exist_ok=True)


@app.route("/static/uploads/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(UPLOAD, filename)

ADMINLAR = {
    x.strip().lower()
    for x in (os.environ.get("ADMIN_LOGINS", "") + ",admin").split(",")
    if x.strip()
}

MAX_ELON = int(os.environ.get("MAX_ELON", 1))
URINISH_LIMIT = 5
URINISH_OYNA = 15 * 60

TARTIB = {
    "yangi": "id DESC",
    "arzon": "narx ASC",
    "qimmat": "narx DESC",
    "reyting": "reyting DESC, sharh_soni DESC",
}

REYTING_SQL = """
    SELECT t.*,
        (SELECT ROUND(AVG(baho), 1) FROM sharhlar WHERE tutor_id = t.id) AS reyting,
        (SELECT COUNT(*) FROM sharhlar WHERE tutor_id = t.id) AS sharh_soni
    FROM tutors t
"""

# ---------------- TARJIMALAR (o'zbek, rus, ingliz) ----------------
TILLAR = ("uz", "ru", "en")

TR = {
    "qidiruv": ("Qidiruv", "Поиск", "Search"),
    "kurs_qosh": ("Kurs qo'shish", "Добавить курс", "Add a course"),
    "kabinet": ("Kabinet", "Кабинет", "Dashboard"),
    "salom": ("Salom, {ism}", "Привет, {ism}", "Hello, {ism}"),
    "chiqish": ("Chiqish", "Выйти", "Log out"),
    "kirish": ("Kirish", "Войти", "Log in"),
    "royxat": ("Ro'yxatdan o'tish", "Регистрация", "Sign up"),
    "som": ("so'm", "сум", "UZS"),
    "soat": ("1 soat", "1 час", "1 hour"),
    "tahrirlash": ("Tahrirlash", "Редактировать", "Edit"),
    "ochirish": ("O'chirish", "Удалить", "Delete"),
    "elon_ochirilsinmi": (
        "Bu e'lon o'chirilsinmi?",
        "Удалить это объявление?",
        "Delete this listing?",
    ),
    "sharh_ochirilsinmi": (
        "Sharh o'chirilsinmi?",
        "Удалить отзыв?",
        "Delete this review?",
    ),
    "hali_sharh_yoq": ("Hali sharh yo'q", "Отзывов пока нет", "No reviews yet"),
    "sharh_n": ("{n} ta sharh", "отзывов: {n}", "{n} reviews"),
    "qongiroq": ("Qo'ng'iroq", "Позвонить", "Call"),
    "kiring": ("Kiring", "Войдите", "Log in"),
    "aloqa_korish": (
        ", aloqa ma'lumotlarini ko'rish uchun.",
        ", чтобы увидеть контакты.",
        " to see contact details.",
    ),
    "yoki": ("yoki", "или", "or"),
    "royxat_oting": ("ro'yxatdan o'ting", "зарегистрируйтесь", "sign up"),
    "sharh_uchun": (
        ", sharh yozish uchun.",
        ", чтобы оставить отзыв.",
        " to leave a review.",
    ),
    "bosh_p": (
        "Fan va shahar bo'yicha o'qituvchi toping yoki o'z kursingizni joylang.",
        "Находите репетиторов по предмету и городу или размещайте свой курс.",
        "Find tutors by subject and city, or post your own course.",
    ),
    "qidirish": ("Qidirish", "Искать", "Search"),
    "yangi_takliflar": ("Yangi takliflar", "Новые предложения", "New listings"),
    "hammasi": ("Hammasi", "Все", "View all"),
    "takliflar_yoq": (
        "Hozircha takliflar yo'q. Birinchi bo'lib kurs qo'shing.",
        "Пока нет предложений. Добавьте курс первым.",
        "No listings yet. Be the first to add a course.",
    ),
    "qid_p": (
        "Ism, fan yoki shahar bo'yicha toping.",
        "Ищите по имени, предмету или городу.",
        "Search by name, subject or city.",
    ),
    "qid_ph": (
        "Masalan: IELTS yoki Toshkent",
        "Например: IELTS или Ташкент",
        "For example: IELTS or Tashkent",
    ),
    "fan": ("Fan", "Предмет", "Subject"),
    "shahar": ("Shahar", "Город", "City"),
    "tartib": ("Tartib", "Сортировка", "Sort by"),
    "barcha_fanlar": ("Barcha fanlar", "Все предметы", "All subjects"),
    "barcha_shaharlar": ("Barcha shaharlar", "Все города", "All cities"),
    "tartib_yangi": ("Yangilari avval", "Сначала новые", "Newest first"),
    "tartib_arzon": ("Arzonidan qimmatiga", "Сначала дешёвые", "Price: low to high"),
    "tartib_qimmat": ("Qimmatidan arzoniga", "Сначала дорогие", "Price: high to low"),
    "tartib_reyting": ("Reyting bo'yicha", "По рейтингу", "Top rated"),
    "natija_n": ("{n} ta natija topildi", "Найдено: {n}", "{n} results found"),
    "hech_narsa": (
        "Hech narsa topilmadi. Filtrni o'zgartiring yoki",
        "Ничего не найдено. Измените фильтр или",
        "Nothing found. Change the filters or",
    ),
    "hammasini_korish": ("hammasini ko'ring", "посмотрите все", "view all"),
    "ozi_haqida": ("O'zi haqida", "О репетиторе", "About"),
    "tavsif_yoq": (
        "Repetitor hali tavsif yozmagan.",
        "Репетитор пока не добавил описание.",
        "The tutor has not added a description yet.",
    ),
    "orqaga": ("Orqaga, qidiruvga", "Назад к поиску", "Back to search"),
    "sharhlar": ("Sharhlar", "Отзывы", "Reviews"),
    "oz_elon_sharh": (
        "Bu sizning e'loningiz, o'zingizga sharh yozib bo'lmaydi.",
        "Это ваше объявление, оставить отзыв самому себе нельзя.",
        "This is your own listing, you cannot review yourself.",
    ),
    "baho_tanlang": ("Bahoni tanlang", "Выберите оценку", "Choose a rating"),
    "sharh_ph": (
        "Sharhingiz (ixtiyoriy)",
        "Ваш отзыв (необязательно)",
        "Your review (optional)",
    ),
    "sharh_yangilash": ("Sharhni yangilash", "Обновить отзыв", "Update review"),
    "sharh_yozish": ("Sharh yozish", "Оставить отзыв", "Write a review"),
    "birinchi_yozing": (
        "Hali sharh yo'q. Birinchi bo'lib yozing.",
        "Отзывов пока нет. Напишите первым.",
        "No reviews yet. Be the first to write one.",
    ),
    "qosh_p": (
        "E'lon hamma uchun ochiq bo'ladi. Telefon va Telegramni faqat kirgan foydalanuvchilar ko'radi.",
        "Объявление видно всем. Телефон и Telegram видят только вошедшие пользователи.",
        "Your listing is public. Phone and Telegram are visible only to logged-in users.",
    ),
    "ph_ism": ("Ismingiz", "Ваше имя", "Your name"),
    "ph_fan": ("Fan", "Предмет", "Subject"),
    "ph_shahar": ("Shahar", "Город", "City"),
    "ph_narx": (
        "Soatiga narx, masalan 80000",
        "Цена за час, например 80000",
        "Price per hour, e.g. 80000",
    ),
    "ph_tel": ("Telefon: 90 123 45 67", "Телефон: 90 123 45 67", "Phone: 90 123 45 67"),
    "ph_tg": (
        "Telegram username, masalan @dilnoza_math (ixtiyoriy)",
        "Telegram username, например @dilnoza_math (необязательно)",
        "Telegram username, e.g. @dilnoza_math (optional)",
    ),
    "ph_tavsif_qosh": (
        "O'zingiz haqingizda: tajriba, usul, natijalar (ixtiyoriy)",
        "О себе: опыт, методика, результаты (необязательно)",
        "About you: experience, method, results (optional)",
    ),
    "ph_tavsif": ("O'zingiz haqingizda", "О себе", "About you"),
    "rasm_lbl": (
        "Rasm (ixtiyoriy, JPG, PNG yoki WEBP, 3 MB gacha)",
        "Фото (необязательно, JPG, PNG или WEBP, до 3 МБ)",
        "Photo (optional, JPG, PNG or WEBP, up to 3 MB)",
    ),
    "elon_joylash": ("E'lon joylash", "Разместить объявление", "Post listing"),
    "tahrir_p": (
        "E'loningiz ma'lumotlarini yangilang.",
        "Обновите данные вашего объявления.",
        "Update your listing details.",
    ),
    "yangi_rasm": (
        "Yangi rasm (eskisi almashadi)",
        "Новое фото (заменит старое)",
        "New photo (replaces the old one)",
    ),
    "rasm_kichik": ("Rasm", "Фото", "Photo"),
    "rasm_format": (
        "(JPG, PNG yoki WEBP, 3 MB gacha)",
        "(JPG, PNG или WEBP, до 3 МБ)",
        "(JPG, PNG or WEBP, up to 3 MB)",
    ),
    "saqlash": ("Saqlash", "Сохранить", "Save"),
    "bekor": ("Bekor qilish", "Отмена", "Cancel"),
    "kirish_p": (
        "Hisobingizga kiring: telefon raqamlarni ko'rish va e'lon joylash uchun.",
        "Войдите в аккаунт, чтобы видеть контакты и размещать объявления.",
        "Log in to see contact details and post listings.",
    ),
    "ph_login": ("Login", "Логин", "Username"),
    "ph_parol": ("Parol", "Пароль", "Password"),
    "hisob_yoq": ("Hisobingiz yo'qmi?", "Нет аккаунта?", "No account yet?"),
    "royxat_cap": ("Ro'yxatdan o'ting", "Зарегистрируйтесь", "Sign up"),
    "royxat_p": (
        "Bepul hisob oching va kurslaringizni joylang.",
        "Создайте бесплатный аккаунт и размещайте свои курсы.",
        "Create a free account and post your courses.",
    ),
    "ph_login_royxat": (
        "Login: lotin harf, raqam, _ (masalan: dilnoza90)",
        "Логин: латиница, цифры, _ (например: dilnoza90)",
        "Username: letters, digits, _ (e.g. dilnoza90)",
    ),
    "ph_parol_royxat": (
        "Parol (kamida 8 ta belgi)",
        "Пароль (не менее 8 символов)",
        "Password (at least 8 characters)",
    ),
    "hisob_bor": ("Hisobingiz bormi?", "Уже есть аккаунт?", "Already have an account?"),
    "kabinet_p": (
        "Salom, {ism}. E'lonlaringiz va sharhlaringiz shu yerda.",
        "Привет, {ism}. Здесь ваши объявления и отзывы.",
        "Hello, {ism}. Your listings and reviews are here.",
    ),
    "elon": ("E'lon", "Объявления", "Listings"),
    "olingan_sharh": ("Olingan sharh", "Полученные отзывы", "Reviews received"),
    "ortacha_reyting": ("O'rtacha reyting", "Средний рейтинг", "Average rating"),
    "mening_elonlarim": ("Mening e'lonlarim", "Мои объявления", "My listings"),
    "yangi_elon": ("Yangi e'lon qo'shish", "Добавить объявление", "Add a listing"),
    "limit_yetdi": (
        "E'lonlar limitiga yetdingiz ({n} ta). Yangisini qo'shish uchun eskisini o'chiring.",
        "Вы достигли лимита объявлений ({n}). Чтобы добавить новое, удалите старое.",
        "You have reached the listing limit ({n}). Delete an old one to add a new one.",
    ),
    "elon_yoq": (
        "Hali e'loningiz yo'q. Birinchi e'loningizni qo'shing.",
        "У вас пока нет объявлений. Добавьте первое.",
        "You have no listings yet. Add your first one.",
    ),
    "yozgan_sharhlarim": ("Yozgan sharhlarim", "Мои отзывы", "My reviews"),
    "sharh_yozmagan": (
        "Hali sharh yozmagansiz. Repetitor sahifasida baho qoldirishingiz mumkin.",
        "Вы ещё не писали отзывы. Оценку можно оставить на странице репетитора.",
        "You have not written any reviews yet. You can rate a tutor on their page.",
    ),
    "bepul_dars": (
        "Birinchi dars bepul",
        "Первый урок бесплатно",
        "First lesson free",
    ),
    "bepul_lbl": (
        "Birinchi dars bepul (sinov darsi beraman)",
        "Первый урок бесплатно (пробный урок)",
        "First lesson is free (trial lesson)",
    ),
    "korish_n": ("{n} marta ko'rilgan", "Просмотров: {n}", "{n} views"),
    "jami_korish": ("Jami ko'rishlar", "Всего просмотров", "Total views"),
    "narx_xato": (
        "Narxni raqam bilan yozing (10 000 dan 5 000 000 gacha)",
        "Укажите цену цифрами (от 10 000 до 5 000 000)",
        "Enter the price as a number (from 10 000 to 5 000 000)",
    ),
    "telefon_xato": (
        "Telefon raqamni to'g'ri yozing, masalan: 90 123 45 67",
        "Введите телефон правильно, например: 90 123 45 67",
        "Enter a valid phone number, for example: 90 123 45 67",
    ),
    "telegram_xato": (
        "Telegram username noto'g'ri. Masalan: @dilnoza_math (5 dan 32 gacha harf, raqam yoki _)",
        "Неверный Telegram username. Например: @dilnoza_math (от 5 до 32 букв, цифр или _)",
        "Invalid Telegram username. Example: @dilnoza_math (5 to 32 letters, digits or _)",
    ),
    "rasm_xato": (
        "Rasm JPG, PNG yoki WEBP bo'lishi kerak (3 MB gacha)",
        "Фото должно быть JPG, PNG или WEBP (до 3 МБ)",
        "The photo must be JPG, PNG or WEBP (up to 3 MB)",
    ),
    "baho_xato": (
        "Bahoni 1 dan 5 gacha tanlang",
        "Выберите оценку от 1 до 5",
        "Choose a rating from 1 to 5",
    ),
    "oz_xato": (
        "O'z e'loningizga sharh yozib bo'lmaydi",
        "Нельзя оставить отзыв на своё объявление",
        "You cannot review your own listing",
    ),
    "csrf_xato": (
        "Xavfsizlik tekshiruvi o'tmadi. Sahifani yangilab, qayta urinib ko'ring.",
        "Проверка безопасности не пройдена. Обновите страницу и попробуйте снова.",
        "Security check failed. Refresh the page and try again.",
    ),
    "limit_xato": (
        "Saytda har bir foydalanuvchiga faqat {n} ta kurs e'lonini joylashga ruxsat berilgan. Yangi e'lon qo'shish uchun avvalgisini tahrirlang yoki o'chiring.",
        "На сайте разрешено размещать только {n} объявление на одного пользователя. Отредактируйте или удалите текущее.",
        "Each user is allowed to post only {n} course listing. Please edit or delete your existing one.",
    ),
    "ism_xato": (
        "Ism 2 dan 80 gacha belgidan iborat bo'lsin",
        "Имя должно содержать от 2 до 80 символов",
        "The name must be 2 to 80 characters long",
    ),
    "fan_xato": (
        "Fan nomi 2 dan 50 gacha belgidan iborat bo'lsin",
        "Название предмета: от 2 до 50 символов",
        "The subject must be 2 to 50 characters long",
    ),
    "shahar_xato": (
        "Shahar nomi 2 dan 50 gacha belgidan iborat bo'lsin",
        "Название города: от 2 до 50 символов",
        "The city must be 2 to 50 characters long",
    ),
    "r_ism_xato": (
        "Ism 2 dan 60 gacha belgidan iborat bo'lsin",
        "Имя должно содержать от 2 до 60 символов",
        "The name must be 2 to 60 characters long",
    ),
    "r_login_xato": (
        "Login 3 dan 30 gacha kichik lotin harf, raqam yoki _ dan iborat bo'lsin",
        "Логин: от 3 до 30 символов, строчные латинские буквы, цифры или _",
        "Username: 3 to 30 characters, lowercase letters, digits or _",
    ),
    "r_parol_xato": (
        "Parol 8 dan 100 gacha belgidan iborat bo'lsin",
        "Пароль должен содержать от 8 до 100 символов",
        "The password must be 8 to 100 characters long",
    ),
    "r_parol_login": (
        "Parol loginga o'xshash bo'lmasin",
        "Пароль не должен совпадать с логином",
        "The password must not be the same as the username",
    ),
    "r_login_band": (
        "Bu login band, boshqasini tanlang",
        "Этот логин занят, выберите другой",
        "This username is taken, choose another",
    ),
    "k_urinish": (
        "Juda ko'p noto'g'ri urinish. 15 daqiqadan keyin qayta urinib ko'ring.",
        "Слишком много неверных попыток. Повторите через 15 минут.",
        "Too many failed attempts. Try again in 15 minutes.",
    ),
    "k_xato": (
        "Login yoki parol noto'g'ri",
        "Неверный логин или пароль",
        "Incorrect username or password",
    ),
    "parol_unut": (
        "Parolni unutdingizmi?",
        "Забыли пароль?",
        "Forgot password?",
    ),
    "parol_tiklash": (
        "Parolni tiklash",
        "Восстановление пароля",
        "Reset password",
    ),
    "parol_tiklash_p": (
        "Hisobingiz ma'lumotlarini tasdiqlab, yangi parol o'rnating",
        "Подтвердите данные аккаунта и установите новый пароль",
        "Verify your account and set a new password",
    ),
    "t_foydalanuvchi_yoq": (
        "Bunday loginli foydalanuvchi topilmadi",
        "Пользователь с таким логином не найден",
        "User with this username was not found",
    ),
    "t_javob_xato": (
        "Xavfsizlik tasdig'i noto'g'ri kiritildi",
        "Ответ безопасности введен неверно",
        "Security answer is incorrect",
    ),
    "t_parol_mos_emas": (
        "Yangi parollar bir-biriga mos kelmadi",
        "Новые пароли не совпадают",
        "New passwords do not match",
    ),
    "t_muvaffaqiyat": (
        "Parolingiz muvaffaqiyatli yangilandi!",
        "Ваш пароль успешно изменен!",
        "Your password has been successfully updated!",
    ),
    "ph_maxfiy_savol": (
        "Xavfsizlik savoli (ixtiyoriy, parolni tiklash uchun)",
        "Секретный вопрос (для восстановления)",
        "Security question (for recovery)",
    ),
    "ph_maxfiy_javob": (
        "Maxfiy javob",
        "Секретный ответ",
        "Secret answer",
    ),
    "yangi_parol": (
        "Yangi parol",
        "Новый пароль",
        "New password",
    ),
    "yangi_parol_tasdiq": (
        "Yangi parolni takrorlang",
        "Повторите новый пароль",
        "Confirm new password",
    ),
}


def joriy_til():
    til_kodi = session.get("lang")
    return til_kodi if til_kodi in ("ru", "en") else "uz"


def tr(key, **kw):
    juft = TR.get(key)
    if juft is None:
        return key
    matn = juft[TILLAR.index(joriy_til())]
    return matn.format(**kw) if kw else matn


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ism TEXT NOT NULL,
            login TEXT NOT NULL UNIQUE,
            parol_hash TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tutors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ism TEXT NOT NULL,
            fan TEXT NOT NULL,
            shahar TEXT NOT NULL,
            narx INTEGER NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sharhlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            baho INTEGER NOT NULL,
            matn TEXT,
            UNIQUE (tutor_id, user_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS urinishlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kalit TEXT NOT NULL,
            vaqt REAL NOT NULL
        )
    """)
    ustunlar = [r["name"] for r in con.execute("PRAGMA table_info(tutors)")]
    if "user_id" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN user_id INTEGER")
    if "telefon" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN telefon TEXT")
    if "tavsif" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN tavsif TEXT")
    if "rasm" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN rasm TEXT")
    if "telegram" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN telegram TEXT")
    if "bepul_dars" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN bepul_dars INTEGER DEFAULT 0")
    if "korishlar" not in ustunlar:
        con.execute("ALTER TABLE tutors ADD COLUMN korishlar INTEGER DEFAULT 0")

    user_ustunlar = [r["name"] for r in con.execute("PRAGMA table_info(users)")]
    if "telefon" not in user_ustunlar:
        con.execute("ALTER TABLE users ADD COLUMN telefon TEXT DEFAULT ''")
    if "maxfiy_savol" not in user_ustunlar:
        con.execute("ALTER TABLE users ADD COLUMN maxfiy_savol TEXT DEFAULT ''")
    if "maxfiy_javob_hash" not in user_ustunlar:
        con.execute("ALTER TABLE users ADD COLUMN maxfiy_javob_hash TEXT DEFAULT ''")

    # Bosh admin hisobi mavjudligini kafolatlash
    admin_bor = con.execute("SELECT id FROM users WHERE login = 'admin'").fetchone()
    if not admin_bor:
        con.execute(
            "INSERT INTO users (ism, login, parol_hash) VALUES (?, ?, ?)",
            ("Bosh Admin", "admin", generate_password_hash("Admin@2026")),
        )

    if con.execute("SELECT COUNT(*) FROM tutors").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO tutors (ism, fan, shahar, narx, tavsif) VALUES (?, ?, ?, ?, ?)",
            [
                ("Dilnoza Karimova", "Matematika", "Toshkent", 90000,
                 "Maktab va DTM tayyorgarligi. Murakkab mavzularni oddiy misollar bilan tushuntiraman."),
                ("Jasur Rahimov", "IELTS", "Samarqand", 120000,
                 "IELTS 8.0. Speaking va Writing bo'yicha har darsda shaxsiy fikr-mulohaza beraman."),
                ("Otabek Ismoilov", "Dasturlash", "Toshkent", 150000,
                 "Python va veb dasturlash noldan. Har oy bitta real loyiha qilamiz."),
            ],
        )
    con.commit()
    con.close()


def narx_olish(matn):
    try:
        n = int(str(matn).replace(" ", ""))
    except (ValueError, AttributeError):
        return None
    if n < 10000 or n > 5000000:
        return None
    return n


def telefon_olish(matn):
    raqam = re.sub(r"\D", "", matn)
    if len(raqam) == 9:
        raqam = "998" + raqam
    if len(raqam) == 12 and raqam.startswith("998"):
        return "+" + raqam
    return None


def telegram_olish(matn):
    """Bo'sh bo'lsa "" qaytaradi, noto'g'ri bo'lsa None, to'g'ri bo'lsa username."""
    matn = matn.strip()
    if not matn:
        return ""
    matn = re.sub(r"^(https?://)?(www\.)?(t\.me/|telegram\.me/)", "", matn, flags=re.I)
    matn = matn.split("?")[0].strip("/").lstrip("@")
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", matn):
        return matn
    return None


def tavsif_olish(matn):
    return matn.strip()[:600]


def maydon_xato(ism, fan, shahar):
    if not (2 <= len(ism) <= 80):
        return tr("ism_xato")
    if not (2 <= len(fan) <= 50):
        return tr("fan_xato")
    if not (2 <= len(shahar) <= 50):
        return tr("shahar_xato")
    return None


def rasm_saqlash(fayl):
    """Rasmni tekshirib saqlaydi. Fayl nomini qaytaradi, noto'g'ri bo'lsa None."""
    bosh = fayl.read(12)
    fayl.seek(0)
    if bosh.startswith(b"\xff\xd8\xff"):
        kengaytma = "jpg"
    elif bosh.startswith(b"\x89PNG\r\n\x1a\n"):
        kengaytma = "png"
    elif bosh[:4] == b"RIFF" and bosh[8:12] == b"WEBP":
        kengaytma = "webp"
    else:
        return None
    nom = uuid.uuid4().hex + "." + kengaytma
    fayl.save(os.path.join(UPLOAD, nom))
    return nom


def rasm_ochirish(nom):
    if nom:
        yol = os.path.join(UPLOAD, os.path.basename(nom))
        if os.path.exists(yol):
            os.remove(yol)


def elon_ochirish(con, tid):
    """E'lonni, uning rasmini va sharhlarini o'chiradi."""
    t = con.execute("SELECT rasm FROM tutors WHERE id = ?", (tid,)).fetchone()
    if t is None:
        return
    rasm_ochirish(t["rasm"])
    con.execute("DELETE FROM sharhlar WHERE tutor_id = ?", (tid,))
    con.execute("DELETE FROM tutors WHERE id = ?", (tid,))


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def csrf_ok():
    yuborilgan = request.form.get("csrf", "")
    saqlangan = session.get("csrf", "")
    if not yuborilgan or not saqlangan:
        return False
    return secrets.compare_digest(yuborilgan.encode(), saqlangan.encode())


def is_admin():
    return session.get("login") in ADMINLAR


def admin_required(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        if not is_admin():
            return redirect("/")
        return f(*args, **kwargs)
    return inner


def sessiya_yangila(**qiymat):
    """Sessiyani tozalaydi, lekin tanlangan tilni saqlab qoladi."""
    til_kodi = session.get("lang")
    session.clear()
    if til_kodi:
        session["lang"] = til_kodi
    session.update(qiymat)


def urinish_soni(con, kalit):
    chegara = time.time() - URINISH_OYNA
    con.execute("DELETE FROM urinishlar WHERE vaqt < ?", (chegara,))
    return con.execute(
        "SELECT COUNT(*) FROM urinishlar WHERE kalit = ?", (kalit,)
    ).fetchone()[0]


@app.before_request
def csrf_himoya():
    if request.method == "POST" and not csrf_ok():
        return tr("csrf_xato"), 400


@app.after_request
def javob_qayta_ishlash(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if resp.mimetype == "text/html":
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        if not resp.direct_passthrough:
            html = resp.get_data(as_text=True)
            belgi = '<input type="hidden" name="csrf" value="%s">' % csrf_token()
            html = re.sub(
                r'(<form\s+method="post"[^>]*>)',
                lambda m: m.group(1) + belgi,
                html,
            )
            resp.set_data(html)
    elif request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@app.errorhandler(413)
def juda_katta(e):
    return tr("rasm_xato"), 413


@app.context_processor
def umumiy():
    return dict(
        user=session.get("user_ism"),
        user_id=session.get("user_id"),
        admin=is_admin(),
        csrf=csrf_token(),
        tr=tr,
        lang=joriy_til(),
        static_version=STATIC_VERSION,
    )


@app.route("/til/<kod>")
def til(kod):
    if kod in TILLAR:
        session["lang"] = kod
    ort = request.args.get("next", "/")
    if not ort.startswith("/") or ort.startswith("//") or "\\" in ort:
        ort = "/"
    if ort.endswith("?"):
        ort = ort[:-1]
    return redirect(ort or "/")


@app.route("/")
def bosh():
    con = db()
    tutors = con.execute(REYTING_SQL + " ORDER BY t.id DESC LIMIT 3").fetchall()
    con.close()
    return render_template("bosh.html", tutors=tutors)


@app.route("/qidiruv")
def qidiruv():
    q = request.args.get("q", "").strip()
    fan = request.args.get("fan", "").strip()
    shahar = request.args.get("shahar", "").strip()
    tartib = request.args.get("tartib", "yangi")
    if tartib not in TARTIB:
        tartib = "yangi"

    sql = REYTING_SQL + " WHERE (t.ism LIKE ? OR t.fan LIKE ? OR t.shahar LIKE ?)"
    params = [f"%{q}%", f"%{q}%", f"%{q}%"]
    if fan:
        sql += " AND t.fan = ? COLLATE NOCASE"
        params.append(fan)
    if shahar:
        sql += " AND t.shahar = ? COLLATE NOCASE"
        params.append(shahar)
    sql += " ORDER BY " + TARTIB[tartib]

    con = db()
    tutors = con.execute(sql, params).fetchall()
    fanlar = [
        r["fan"]
        for r in con.execute(
            "SELECT MIN(fan) AS fan FROM tutors GROUP BY LOWER(fan) ORDER BY LOWER(fan)"
        )
    ]
    shaharlar = [
        r["shahar"]
        for r in con.execute(
            "SELECT MIN(shahar) AS shahar FROM tutors GROUP BY LOWER(shahar) ORDER BY LOWER(shahar)"
        )
    ]
    con.close()
    return render_template(
        "qidiruv.html",
        tutors=tutors,
        q=q,
        fan=fan,
        shahar=shahar,
        tartib=tartib,
        fanlar=fanlar,
        shaharlar=shaharlar,
        tartiblar=list(TARTIB),
    )


XATO_KODLAR = {"oz": "oz_xato", "baho": "baho_xato"}


def repetitor_sahifa(tid, xato=""):
    con = db()
    t = con.execute(REYTING_SQL + " WHERE t.id = ?", (tid,)).fetchone()
    if t is None:
        con.close()
        return redirect("/qidiruv")

    # Ko'rishlarni hisoblash: bir brauzer bir e'lonni bir marta, egasi sanalmaydi
    ega = t["user_id"] is not None and t["user_id"] == session.get("user_id")
    korilgan = session.get("korilgan", [])
    if not ega and tid not in korilgan:
        con.execute(
            "UPDATE tutors SET korishlar = COALESCE(korishlar, 0) + 1 WHERE id = ?",
            (tid,),
        )
        con.commit()
        korilgan.append(tid)
        session["korilgan"] = korilgan[-200:]

    sharhlar = con.execute(
        "SELECT s.*, u.ism AS muallif FROM sharhlar s JOIN users u ON u.id = s.user_id "
        "WHERE s.tutor_id = ? ORDER BY s.id DESC",
        (tid,),
    ).fetchall()
    mening = None
    if "user_id" in session:
        mening = con.execute(
            "SELECT * FROM sharhlar WHERE tutor_id = ? AND user_id = ?",
            (tid, session["user_id"]),
        ).fetchone()
    con.close()
    return render_template(
        "repetitor.html", t=t, sharhlar=sharhlar, mening=mening, xato=xato
    )


@app.route("/repetitor/<int:tid>")
def repetitor(tid):
    kod = request.args.get("x", "")
    xato = tr(XATO_KODLAR[kod]) if kod in XATO_KODLAR else ""
    return repetitor_sahifa(tid, xato)


@app.route("/sharh/<int:tid>", methods=["POST"])
def sharh_yoz(tid):
    if "user_id" not in session:
        return redirect("/kirish")
    con = db()
    t = con.execute("SELECT user_id FROM tutors WHERE id = ?", (tid,)).fetchone()
    if t is None:
        con.close()
        return redirect("/qidiruv")
    if t["user_id"] == session["user_id"]:
        con.close()
        return redirect("/repetitor/" + str(tid) + "?x=oz")
    try:
        baho = int(request.form.get("baho", ""))
    except ValueError:
        baho = 0
    if baho < 1 or baho > 5:
        con.close()
        return redirect("/repetitor/" + str(tid) + "?x=baho")
    matn = request.form.get("matn", "").strip()[:500]
    con.execute(
        "INSERT INTO sharhlar (tutor_id, user_id, baho, matn) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (tutor_id, user_id) DO UPDATE SET baho = excluded.baho, matn = excluded.matn",
        (tid, session["user_id"], baho, matn),
    )
    con.commit()
    con.close()
    return redirect("/repetitor/" + str(tid) + "#sharhlar")


@app.route("/sharh-ochir/<int:sid>", methods=["POST"])
def sharh_ochir(sid):
    if "user_id" not in session:
        return redirect("/kirish")
    con = db()
    if is_admin():
        s = con.execute("SELECT tutor_id FROM sharhlar WHERE id = ?", (sid,)).fetchone()
    else:
        s = con.execute(
            "SELECT tutor_id FROM sharhlar WHERE id = ? AND user_id = ?",
            (sid, session["user_id"]),
        ).fetchone()
    if s is None:
        con.close()
        return redirect("/qidiruv")
    con.execute("DELETE FROM sharhlar WHERE id = ?", (sid,))
    con.commit()
    con.close()
    return redirect("/repetitor/" + str(s["tutor_id"]) + "#sharhlar")


@app.route("/qosh", methods=["GET", "POST"])
def qosh():
    if "user_id" not in session:
        return redirect("/kirish")

    con = db()
    soni = con.execute(
        "SELECT COUNT(*) FROM tutors WHERE user_id = ?", (session["user_id"],)
    ).fetchone()[0]
    con.close()

    if soni >= MAX_ELON and not is_admin():
        return render_template(
            "qosh.html",
            xato=tr("limit_xato", n=MAX_ELON),
            limit_yetdi=True,
        )

    if request.method == "GET":
        return render_template("qosh.html", xato="")
    ism = request.form["ism"].strip()
    fan = request.form["fan"].strip()
    shahar = request.form["shahar"].strip()
    tavsif = tavsif_olish(request.form.get("tavsif", ""))
    bepul = 1 if request.form.get("bepul") else 0
    xato = maydon_xato(ism, fan, shahar)
    if xato:
        return render_template("qosh.html", xato=xato)
    narx = narx_olish(request.form["narx"])
    if narx is None:
        return render_template("qosh.html", xato=tr("narx_xato"))
    telefon = telefon_olish(request.form["telefon"])
    if telefon is None:
        return render_template("qosh.html", xato=tr("telefon_xato"))
    telegram = telegram_olish(request.form.get("telegram", ""))
    if telegram is None:
        return render_template("qosh.html", xato=tr("telegram_xato"))
    rasm = None
    fayl = request.files.get("rasm")
    if fayl and fayl.filename:
        rasm = rasm_saqlash(fayl)
        if rasm is None:
            return render_template("qosh.html", xato=tr("rasm_xato"))
    con = db()
    con.execute(
        "INSERT INTO tutors (ism, fan, shahar, narx, telefon, telegram, tavsif, rasm, bepul_dars, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ism, fan, shahar, narx, telefon, telegram, tavsif, rasm, bepul, session["user_id"]),
    )
    con.commit()
    con.close()
    return redirect("/kabinet")


@app.route("/royxat", methods=["GET", "POST"])
def royxat():
    if request.method == "GET":
        return render_template("royxat.html", xato="")
    ism = request.form["ism"].strip()
    login = request.form["login"].strip().lower()
    parol = request.form["parol"]
    maxfiy_savol = request.form.get("maxfiy_savol", "").strip()[:100]
    maxfiy_javob = request.form.get("maxfiy_javob", "").strip()[:100]
    telefon = request.form.get("telefon", "").strip()[:30]

    if not (2 <= len(ism) <= 60):
        return render_template("royxat.html", xato=tr("r_ism_xato"))
    if not re.fullmatch(r"[a-z0-9_]{3,30}", login):
        return render_template("royxat.html", xato=tr("r_login_xato"))
    if len(parol) < 8 or len(parol) > 100:
        return render_template("royxat.html", xato=tr("r_parol_xato"))
    if parol.lower() == login:
        return render_template("royxat.html", xato=tr("r_parol_login"))
    
    javob_hash = generate_password_hash(maxfiy_javob.lower()) if maxfiy_javob else ""
    con = db()
    try:
        cur = con.execute(
            "INSERT INTO users (ism, login, parol_hash, telefon, maxfiy_savol, maxfiy_javob_hash) VALUES (?, ?, ?, ?, ?, ?)",
            (ism, login, generate_password_hash(parol), telefon, maxfiy_savol, javob_hash),
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        return render_template("royxat.html", xato=tr("r_login_band"))
    con.close()
    sessiya_yangila(user_id=cur.lastrowid, user_ism=ism, login=login)
    return redirect("/")


@app.route("/tiklash", methods=["GET", "POST"])
def tiklash():
    if request.method == "GET":
        login = request.args.get("login", "").strip().lower()
        if login:
            con = db()
            u = con.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
            con.close()
            if u:
                return render_template(
                    "tiklash.html",
                    step=2,
                    login=u["login"],
                    ism=u["ism"],
                    maxfiy_savol=u["maxfiy_savol"],
                    xato="",
                )
        return render_template("tiklash.html", step=1, login="", xato="")

    action = request.form.get("action", "")
    login = request.form.get("login", "").strip().lower()[:50]

    if not login:
        return render_template("tiklash.html", step=1, login="", xato=tr("r_login_xato"))

    con = db()
    u = con.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
    if u is None:
        con.close()
        return render_template("tiklash.html", step=1, login=login, xato=tr("t_foydalanuvchi_yoq"))

    # 1-qadam: faqat login yuborilgan
    if action == "find" or "yangi_parol" not in request.form:
        con.close()
        return render_template(
            "tiklash.html",
            step=2,
            login=u["login"],
            ism=u["ism"],
            maxfiy_savol=u["maxfiy_savol"],
            xato="",
        )

    # 2-qadam: parolni yangilash so'rovi
    if urinish_soni(con, "reset_" + login) >= URINISH_LIMIT:
        con.commit()
        con.close()
        return render_template(
            "tiklash.html",
            step=2,
            login=u["login"],
            ism=u["ism"],
            maxfiy_savol=u["maxfiy_savol"],
            xato=tr("k_urinish"),
        ), 429

    javob = request.form.get("javob", "").strip()
    yangi_parol = request.form.get("yangi_parol", "")
    yangi_parol2 = request.form.get("yangi_parol2", "")

    tasdiqlandi = False

    # 1. Maxfiy javob hashi tekshiruvi
    if u["maxfiy_javob_hash"] and javob:
        if check_password_hash(u["maxfiy_javob_hash"], javob.lower()):
            tasdiqlandi = True

    # 2. Foydalanuvchi telefon raqami tekshiruvi
    if not tasdiqlandi and u["telefon"] and javob:
        toza_javob = re.sub(r"\D", "", javob)
        toza_tel = re.sub(r"\D", "", u["telefon"])
        if toza_javob and toza_tel and (toza_javob in toza_tel or toza_tel in toza_javob):
            tasdiqlandi = True

    # 3. Foydalanuvchining to'liq ismi tekshiruvi
    if not tasdiqlandi and javob:
        if javob.lower() == u["ism"].strip().lower():
            tasdiqlandi = True

    # 4. Foydalanuvchiga tegishli repetitor e'lonidagi telefon yoki telegram
    if not tasdiqlandi and javob:
        tutors = con.execute("SELECT telefon, telegram FROM tutors WHERE user_id = ?", (u["id"],)).fetchall()
        for tut in tutors:
            if tut["telefon"] and re.sub(r"\D", "", javob) and re.sub(r"\D", "", javob) in re.sub(r"\D", "", tut["telefon"]):
                tasdiqlandi = True
                break
            if tut["telegram"] and javob.lstrip("@").lower() == tut["telegram"].lstrip("@").lower():
                tasdiqlandi = True
                break

    # 5. Admin hisobi
    if not tasdiqlandi and u["login"] in ADMINLAR and javob:
        if javob == os.environ.get("ADMIN_SECRET", "Admin@2026"):
            tasdiqlandi = True

    if not tasdiqlandi:
        con.execute("INSERT INTO urinishlar (kalit, vaqt) VALUES (?, ?)", ("reset_" + login, time.time()))
        con.commit()
        con.close()
        return render_template(
            "tiklash.html",
            step=2,
            login=u["login"],
            ism=u["ism"],
            maxfiy_savol=u["maxfiy_savol"],
            xato=tr("t_javob_xato"),
        )

    # Parol validatsiyasi
    if len(yangi_parol) < 8 or len(yangi_parol) > 100:
        con.close()
        return render_template(
            "tiklash.html",
            step=2,
            login=u["login"],
            ism=u["ism"],
            maxfiy_savol=u["maxfiy_savol"],
            xato=tr("r_parol_xato"),
        )
    if yangi_parol.lower() == login:
        con.close()
        return render_template(
            "tiklash.html",
            step=2,
            login=u["login"],
            ism=u["ism"],
            maxfiy_savol=u["maxfiy_savol"],
            xato=tr("r_parol_login"),
        )
    if yangi_parol != yangi_parol2:
        con.close()
        return render_template(
            "tiklash.html",
            step=2,
            login=u["login"],
            ism=u["ism"],
            maxfiy_savol=u["maxfiy_savol"],
            xato=tr("t_parol_mos_emas"),
        )

    # Parolni yangilash
    con.execute(
        "UPDATE users SET parol_hash = ? WHERE id = ?",
        (generate_password_hash(yangi_parol), u["id"]),
    )
    con.execute("DELETE FROM urinishlar WHERE kalit = ? OR kalit = ?", (login, "reset_" + login))
    con.commit()
    con.close()

    sessiya_yangila(user_id=u["id"], user_ism=u["ism"], login=u["login"])
    return redirect("/kabinet?xabar=parol_yangilandi")


@app.route("/kirish", methods=["GET", "POST"])
def kirish():
    if request.method == "GET":
        return render_template("kirish.html", xato="")
    login = request.form["login"].strip().lower()[:50]
    parol = request.form["parol"][:200]
    con = db()
    if urinish_soni(con, login) >= URINISH_LIMIT:
        con.commit()
        con.close()
        return render_template("kirish.html", xato=tr("k_urinish"), login=login), 429
    u = con.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
    if u is None or not check_password_hash(u["parol_hash"], parol):
        con.execute(
            "INSERT INTO urinishlar (kalit, vaqt) VALUES (?, ?)", (login, time.time())
        )
        con.commit()
        con.close()
        return render_template("kirish.html", xato=tr("k_xato"), login=login)
    con.execute("DELETE FROM urinishlar WHERE kalit = ?", (login,))
    con.commit()
    con.close()
    sessiya_yangila(user_id=u["id"], user_ism=u["ism"], login=u["login"])
    return redirect("/")


@app.route("/chiqish")
def chiqish():
    sessiya_yangila()
    return redirect("/")


@app.route("/kabinet")
def kabinet():
    if "user_id" not in session:
        return redirect("/kirish")
    con = db()
    tutors = con.execute(
        REYTING_SQL + " WHERE t.user_id = ? ORDER BY t.id DESC", (session["user_id"],)
    ).fetchall()
    olingan = con.execute(
        "SELECT COUNT(*) AS soni, ROUND(AVG(s.baho), 1) AS reyting "
        "FROM sharhlar s JOIN tutors t ON t.id = s.tutor_id WHERE t.user_id = ?",
        (session["user_id"],),
    ).fetchone()
    yozgan = con.execute(
        "SELECT s.id, s.baho, s.matn, t.id AS tid, t.ism AS repetitor "
        "FROM sharhlar s JOIN tutors t ON t.id = s.tutor_id "
        "WHERE s.user_id = ? ORDER BY s.id DESC",
        (session["user_id"],),
    ).fetchall()
    con.close()
    stat = {
        "elon": len(tutors),
        "sharh": olingan["soni"],
        "reyting": olingan["reyting"],
        "korish": sum((t["korishlar"] or 0) for t in tutors),
    }
    return render_template(
        "kabinet.html", tutors=tutors, stat=stat, yozgan=yozgan, limit=MAX_ELON
    )


@app.route("/tahrir/<int:tid>", methods=["GET", "POST"])
def tahrir(tid):
    if "user_id" not in session:
        return redirect("/kirish")
    con = db()
    if is_admin():
        t = con.execute("SELECT * FROM tutors WHERE id = ?", (tid,)).fetchone()
    else:
        t = con.execute(
            "SELECT * FROM tutors WHERE id = ? AND user_id = ?", (tid, session["user_id"])
        ).fetchone()
    if t is None:
        con.close()
        return redirect("/qidiruv")
    if request.method == "GET":
        con.close()
        return render_template("tahrir.html", t=t, xato="")
    ism = request.form["ism"].strip()
    fan = request.form["fan"].strip()
    shahar = request.form["shahar"].strip()
    tavsif = tavsif_olish(request.form.get("tavsif", ""))
    bepul = 1 if request.form.get("bepul") else 0
    xato = maydon_xato(ism, fan, shahar)
    if xato:
        con.close()
        return render_template("tahrir.html", t=t, xato=xato)
    narx = narx_olish(request.form["narx"])
    if narx is None:
        con.close()
        return render_template("tahrir.html", t=t, xato=tr("narx_xato"))
    telefon = telefon_olish(request.form["telefon"])
    if telefon is None:
        con.close()
        return render_template("tahrir.html", t=t, xato=tr("telefon_xato"))
    telegram = telegram_olish(request.form.get("telegram", ""))
    if telegram is None:
        con.close()
        return render_template("tahrir.html", t=t, xato=tr("telegram_xato"))
    rasm = t["rasm"]
    fayl = request.files.get("rasm")
    if fayl and fayl.filename:
        yangi = rasm_saqlash(fayl)
        if yangi is None:
            con.close()
            return render_template("tahrir.html", t=t, xato=tr("rasm_xato"))
        rasm_ochirish(rasm)
        rasm = yangi
    if is_admin():
        con.execute(
            "UPDATE tutors SET ism = ?, fan = ?, shahar = ?, narx = ?, telefon = ?, telegram = ?, "
            "tavsif = ?, rasm = ?, bepul_dars = ? WHERE id = ?",
            (ism, fan, shahar, narx, telefon, telegram, tavsif, rasm, bepul, tid),
        )
    else:
        con.execute(
            "UPDATE tutors SET ism = ?, fan = ?, shahar = ?, narx = ?, telefon = ?, telegram = ?, "
            "tavsif = ?, rasm = ?, bepul_dars = ? WHERE id = ? AND user_id = ?",
            (ism, fan, shahar, narx, telefon, telegram, tavsif, rasm, bepul, tid, session["user_id"]),
        )
    con.commit()
    con.close()
    return redirect("/repetitor/" + str(tid))


@app.route("/ochir/<int:tid>", methods=["POST"])
def ochir(tid):
    if "user_id" not in session:
        return redirect("/kirish")
    con = db()
    if is_admin():
        t = con.execute("SELECT id FROM tutors WHERE id = ?", (tid,)).fetchone()
    else:
        t = con.execute(
            "SELECT id FROM tutors WHERE id = ? AND user_id = ?", (tid, session["user_id"])
        ).fetchone()
    if t:
        elon_ochirish(con, tid)
        con.commit()
    con.close()
    return redirect("/kabinet")


@app.route("/admin")
@admin_required
def admin():
    con = db()
    stat = {
        "users": con.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "tutors": con.execute("SELECT COUNT(*) FROM tutors").fetchone()[0],
        "sharhlar": con.execute("SELECT COUNT(*) FROM sharhlar").fetchone()[0],
    }
    tutors = con.execute(REYTING_SQL + " ORDER BY t.id DESC LIMIT 50").fetchall()
    sharhlar = con.execute(
        "SELECT s.*, u.ism AS muallif, t.ism AS repetitor "
        "FROM sharhlar s JOIN users u ON u.id = s.user_id JOIN tutors t ON t.id = s.tutor_id "
        "ORDER BY s.id DESC LIMIT 50"
    ).fetchall()
    users = con.execute(
        "SELECT u.*, (SELECT COUNT(*) FROM tutors WHERE user_id = u.id) AS elonlar "
        "FROM users u ORDER BY u.id DESC LIMIT 50"
    ).fetchall()
    con.close()
    return render_template(
        "admin.html",
        stat=stat,
        tutors=tutors,
        sharhlar=sharhlar,
        users=users,
        adminlar=ADMINLAR,
        xabar=request.args.get("xabar", ""),
    )


@app.route("/admin/elon-ochir/<int:tid>", methods=["POST"])
@admin_required
def admin_elon_ochir(tid):
    con = db()
    elon_ochirish(con, tid)
    con.commit()
    con.close()
    return redirect("/admin?xabar=E'lon o'chirildi")


@app.route("/admin/sharh-ochir/<int:sid>", methods=["POST"])
@admin_required
def admin_sharh_ochir(sid):
    con = db()
    con.execute("DELETE FROM sharhlar WHERE id = ?", (sid,))
    con.commit()
    con.close()
    return redirect("/admin?xabar=Sharh o'chirildi")


@app.route("/admin/user-ochir/<int:uid>", methods=["POST"])
@admin_required
def admin_user_ochir(uid):
    con = db()
    u = con.execute("SELECT login FROM users WHERE id = ?", (uid,)).fetchone()
    if u is None:
        con.close()
        return redirect("/admin")
    if u["login"] in ADMINLAR:
        con.close()
        return redirect("/admin?xabar=Adminni o'chirib bo'lmaydi")
    for t in con.execute("SELECT id FROM tutors WHERE user_id = ?", (uid,)).fetchall():
        elon_ochirish(con, t["id"])
    con.execute("DELETE FROM sharhlar WHERE user_id = ?", (uid,))
    con.execute("DELETE FROM users WHERE id = ?", (uid,))
    con.commit()
    con.close()
    return redirect("/admin?xabar=Foydalanuvchi va uning e'lonlari o'chirildi")


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("DEBUG") == "1")