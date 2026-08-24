import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = "8508551199:AAEfhVkgo5HR8gD7bA18oFjtRQSX2RuC7Tg"
ADMIN_ID = 6807924261

REFERRAL_POINTS = 1


def stock_text(stock):
    return "∞ نامحدود" if stock < 0 else str(stock)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    points INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    referred_by INTEGER DEFAULT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    image_id TEXT DEFAULT '',
    required_points INTEGER DEFAULT 0,
    stock INTEGER DEFAULT 0,
    login TEXT DEFAULT '',
    password TEXT DEFAULT '',
    active INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    invite_link TEXT DEFAULT '',
    active INTEGER DEFAULT 1
)
""")

# Statistics / delivery history
cursor.execute("""
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    points_spent INTEGER DEFAULT 0,
    delivered_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# Safe migration for old bot.db files.
def ensure_column(table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

ensure_column("users", "created_at", "TEXT")

cursor.execute("UPDATE users SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")

db.commit()


# =========================================================
# BOT
# =========================================================

if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
    raise RuntimeError("BOT_TOKEN را در ابتدای app.py وارد کن")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


# =========================================================
# TEMPORARY ADMIN STATES
# =========================================================

admin_state = {}


# =========================================================
# PERSISTENT START KEYBOARD
# =========================================================

def start_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("/Start"))
    return keyboard


# =========================================================
# USER MENU
# =========================================================

def main_menu(user_id):

    keyboard = InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        InlineKeyboardButton(
            "🎁 انتخاب اکانت",
            callback_data="accounts"
        ),
        InlineKeyboardButton(
            "👤 حساب من",
            callback_data="profile"
        ),
        InlineKeyboardButton(
            "🔗 دعوت دوستان",
            callback_data="referral"
        ),
        InlineKeyboardButton(
            "📢 کانال‌های ما",
            callback_data="channels"
        )
    )

    if user_id == ADMIN_ID:
        keyboard.add(
            InlineKeyboardButton(
                "👑 پنل مدیریت",
                callback_data="admin_panel"
            )
        )

    return keyboard


# =========================================================
# ADMIN MENU
# =========================================================

def admin_menu():

    keyboard = InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        InlineKeyboardButton(
            "🎁 مدیریت اکانت‌ها",
            callback_data="manage_accounts"
        ),
        InlineKeyboardButton(
            "📢 جوین اجباری",
            callback_data="manage_channels"
        ),
        InlineKeyboardButton(
            "📊 آمار",
            callback_data="statistics"
        ),
        InlineKeyboardButton(
            "♻️ ریست آمار",
            callback_data="reset_statistics"
        ),
        InlineKeyboardButton(
            "📣 ارسال پیام همگانی",
            callback_data="broadcast"
        ),
        InlineKeyboardButton(
            "📢 ارسال به کانال‌ها",
            callback_data="channel_broadcast"
        ),
        InlineKeyboardButton(
            "🏠 منوی اصلی",
            callback_data="back_main"
        )
    )

    return keyboard


# =========================================================
# USER CREATION
# =========================================================

def create_user(user, referred_by=None):

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.id,)
    )

    exists = cursor.fetchone()

    if exists:
        return False

    cursor.execute("""
    INSERT INTO users
    (user_id, username, first_name, referred_by)
    VALUES (?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        referred_by
    ))

    db.commit()

    return True


# =========================================================
# START
# =========================================================

async def send_start(message: types.Message):
    user = message.from_user

    referred_by = None
    args = message.get_args()

    if args.startswith("ref_"):
        try:
            ref_id = int(args.replace("ref_", ""))
            if ref_id != user.id:
                referred_by = ref_id
        except ValueError:
            pass

    is_new = create_user(user, referred_by)

    if is_new and referred_by:
        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (referred_by,)
        )
        if cursor.fetchone():
            cursor.execute("""
                UPDATE users
                SET points = points + ?,
                    referrals = referrals + 1
                WHERE user_id = ?
            """, (REFERRAL_POINTS, referred_by))
            db.commit()
            try:
                await bot.send_message(
                    referred_by,
                    f"🎉 یک نفر با لینک دعوت شما وارد شد!\n\n"
                    f"⭐ +{REFERRAL_POINTS} امتیاز دریافت کردی."
                )
            except Exception:
                pass

    # Every /start (including the permanent keyboard button) checks force-join.
    ok, join_kb = await require_force_join(user.id)

    if not ok:
        await message.answer(
            "⛔ برای استفاده از ربات، ابتدا در کانال‌های زیر عضو شو:",
            reply_markup=join_kb
        )
    else:
        await message.answer(
            "سلام 👋\n\n"
            "به ربات خوش آمدی.\n"
            "از منوی زیر استفاده کن:",
            reply_markup=main_menu(user.id)
        )

    await message.answer(
        "🚀 برای اجرای دوباره ربات، دکمه زیر را بزن.",
        reply_markup=start_keyboard()
    )


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await send_start(message)


@dp.message_handler(
    lambda m: (m.text or "").strip() == "🚀 استارت ربات",
    content_types=types.ContentType.TEXT
)
async def persistent_start(message: types.Message):
    await send_start(message)


# =========================================================
# PROFILE
# =========================================================

@dp.callback_query_handler(lambda c: c.data == "profile")
async def profile(call: types.CallbackQuery):

    ok, keyboard_join = await require_force_join(call.from_user.id)
    if not ok:
        await call.message.answer("⛔ ابتدا باید در کانال‌های اجباری عضو شوی.", reply_markup=keyboard_join)
        await call.answer()
        return

    cursor.execute("""
    SELECT points, referrals
    FROM users
    WHERE user_id = ?
    """, (
        call.from_user.id,
    ))

    user = cursor.fetchone()

    if not user:

        await call.answer(
            "ابتدا /start را بزن.",
            show_alert=True
        )

        return

    await call.message.edit_text(
        "👤 حساب من\n\n"
        f"⭐ امتیاز: {user[0]}\n"
        f"👥 دعوت موفق: {user[1]}",
        reply_markup=main_menu(call.from_user.id)
    )

    await call.answer()


# =========================================================
# REFERRAL
# =========================================================

@dp.callback_query_handler(lambda c: c.data == "referral")
async def referral(call: types.CallbackQuery):

    ok, keyboard_join = await require_force_join(call.from_user.id)
    if not ok:
        await call.message.answer("⛔ ابتدا باید در کانال‌های اجباری عضو شوی.", reply_markup=keyboard_join)
        await call.answer()
        return

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{call.from_user.id}"
    )

    await call.message.edit_text(
        "🔗 لینک دعوت اختصاصی شما:\n\n"
        f"{link}\n\n"
        f"⭐ هر دعوت موفق = {REFERRAL_POINTS} امتیاز",
        reply_markup=main_menu(call.from_user.id)
    )

    await call.answer()


# =========================================================
# FORCE JOIN CHECK
# =========================================================

async def check_channels(user_id):

    cursor.execute("""
    SELECT chat_id, title, invite_link
    FROM channels
    WHERE active = 1
    """)

    channels = cursor.fetchall()

    not_joined = []

    for chat_id, title, invite_link in channels:

        try:

            member = await bot.get_chat_member(
                chat_id,
                user_id
            )

            if member.status in [
                "left",
                "kicked"
            ]:

                not_joined.append(
                    (title, invite_link)
                )

        except Exception:

            not_joined.append(
                (title, invite_link)
            )

    return not_joined


# =========================================================
# FORCE JOIN BUTTON
# =========================================================

def join_keyboard(channels):

    keyboard = InlineKeyboardMarkup(row_width=1)

    for title, link in channels:

        if link:

            keyboard.add(
                InlineKeyboardButton(
                    f"📢 عضویت در {title}",
                    url=link
                )
            )

    keyboard.add(
        InlineKeyboardButton(
            "✅ بررسی عضویت",
            callback_data="check_join"
        )
    )

    return keyboard


async def require_force_join(user_id):
    not_joined = await check_channels(user_id)
    if not_joined:
        return False, join_keyboard(not_joined)
    return True, None


# =========================================================
# ACCOUNTS LIST
# =========================================================

@dp.callback_query_handler(lambda c: c.data == "accounts")
async def accounts(call: types.CallbackQuery):

    ok, keyboard_join = await require_force_join(call.from_user.id)
    if not ok:
        await call.message.answer("⛔ ابتدا باید در کانال‌های اجباری عضو شوی.", reply_markup=keyboard_join)
        await call.answer()
        return

    cursor.execute("""
    SELECT id, name, required_points, stock
    FROM accounts
    WHERE active = 1
    ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    if not rows:

        await call.message.edit_text(
            "🎁 اکانت‌ها\n\n"
            "فعلاً هیچ اکانتی موجود نیست.",
            reply_markup=main_menu(call.from_user.id)
        )

        await call.answer()

        return

    keyboard = InlineKeyboardMarkup(row_width=1)

    for account_id, name, points, stock in rows:

        keyboard.add(
            InlineKeyboardButton(
                f"🎁 {name} | ⭐ {points} | 📦 {stock_text(stock)}",
                callback_data=f"account_{account_id}"
            )
        )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="back_main"
        )
    )

    await call.message.edit_text(
        "🎁 انتخاب اکانت\n\n"
        "اکانت موردنظر را انتخاب کن:",
        reply_markup=keyboard
    )

    await call.answer()


# =========================================================
# ACCOUNT DETAILS
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data.startswith("account_")
)
async def account_details(call: types.CallbackQuery):

    account_id = int(
        call.data.split("_")[1]
    )

    cursor.execute("""
    SELECT name, description, image_id,
           required_points, stock
    FROM accounts
    WHERE id = ? AND active = 1
    """, (
        account_id,
    ))

    account = cursor.fetchone()

    if not account:

        await call.answer(
            "اکانت پیدا نشد.",
            show_alert=True
        )

        return

    name, description, image_id, required_points, stock = account

    text = (
        f"🎁 {name}\n\n"
        f"{description}\n\n"
        f"⭐ امتیاز لازم: {required_points}\n"
        f"📦 موجودی: {stock_text(stock)}"
    )

    keyboard = InlineKeyboardMarkup()

    if stock > 0:

        keyboard.add(
            InlineKeyboardButton(
                "🎁 دریافت اکانت",
                callback_data=f"get_{account_id}"
            )
        )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="accounts"
        )
    )

    if image_id:

        try:

            await call.message.delete()

            await bot.send_photo(
                call.from_user.id,
                image_id,
                caption=text,
                reply_markup=keyboard
            )

        except Exception:

            await call.message.edit_text(
                text,
                reply_markup=keyboard
            )

    else:

        await call.message.edit_text(
            text,
            reply_markup=keyboard
        )

    await call.answer()


# =========================================================
# GET ACCOUNT
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data.startswith("get_")
)
async def get_account(call: types.CallbackQuery):

    account_id = int(
        call.data.split("_")[1]
    )

    # Check force join

    not_joined = await check_channels(
        call.from_user.id
    )

    if not_joined:

        await call.message.answer(
            "⛔ برای دریافت اکانت باید ابتدا در کانال‌های زیر عضو شوی:",
            reply_markup=join_keyboard(not_joined)
        )

        await call.answer()

        return

    cursor.execute("""
    SELECT name, required_points, stock, login, password
    FROM accounts
    WHERE id = ? AND active = 1
    """, (
        account_id,
    ))

    account = cursor.fetchone()

    if not account:

        await call.answer(
            "اکانت موجود نیست.",
            show_alert=True
        )

        return

    name, required_points, stock, login, password = account

    cursor.execute(
        "SELECT points FROM users WHERE user_id = ?",
        (call.from_user.id,)
    )

    user = cursor.fetchone()

    if not user:

        await call.answer(
            "ابتدا /start را بزن.",
            show_alert=True
        )

        return

    points = user[0]

    if points < required_points:

        await call.answer(
            f"❌ امتیاز کافی نداری.\n"
            f"امتیاز لازم: {required_points}\n"
            f"امتیاز فعلی: {points}",
            show_alert=True
        )

        return

    if stock == 0:

        await call.answer(
            "❌ موجودی این اکانت تمام شده.",
            show_alert=True
        )

        return

    # Deduct points and stock

    cursor.execute("""
    UPDATE users
    SET points = points - ?
    WHERE user_id = ?
    """, (
        required_points,
        call.from_user.id
    ))

    if stock > 0:
        cursor.execute("""
        UPDATE accounts
        SET stock = stock - 1
        WHERE id = ? AND stock > 0
        """, (account_id,))

    cursor.execute("""
        INSERT INTO deliveries (user_id, account_id, points_spent)
        VALUES (?, ?, ?)
    """, (call.from_user.id, account_id, required_points))

    db.commit()

    await call.message.answer(
        "🎉 اکانت با موفقیت دریافت شد!\n\n"
        f"🎁 {name}\n\n"
        f"📧 Login:\n{login}\n\n"
        f"🔐 Password:\n{password}\n\n"
        "⚠️ اطلاعات را در اختیار دیگران قرار نده."
    )

    await call.answer(
        "✅ اکانت تحویل داده شد."
    )


# =========================================================
# CHECK JOIN
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "check_join"
)
async def check_join(call: types.CallbackQuery):

    not_joined = await check_channels(
        call.from_user.id
    )

    if not_joined:

        await call.answer(
            "❌ هنوز در همه کانال‌ها عضو نشده‌ای.",
            show_alert=True
        )

        return

    await call.message.edit_text(
        "✅ عضویت شما تأیید شد.\n\n"
        "حالا می‌توانی اکانت موردنظرت را دریافت کنی.",
        reply_markup=main_menu(call.from_user.id)
    )

    await call.answer()


# =========================================================
# CHANNELS
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "channels"
)
async def channels(call: types.CallbackQuery):

    ok, keyboard_join = await require_force_join(call.from_user.id)
    if not ok:
        await call.message.answer("⛔ ابتدا باید در کانال‌های اجباری عضو شوی.", reply_markup=keyboard_join)
        await call.answer()
        return

    cursor.execute("""
    SELECT title, invite_link
    FROM channels
    WHERE active = 1
    """)

    rows = cursor.fetchall()

    keyboard = InlineKeyboardMarkup(row_width=1)

    for title, link in rows:

        if link:

            keyboard.add(
                InlineKeyboardButton(
                    f"📢 {title}",
                    url=link
                )
            )

    keyboard.add(
        InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="back_main"
        )
    )

    await call.message.edit_text(
        "📢 کانال‌های ما",
        reply_markup=keyboard
    )

    await call.answer()


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message_handler(commands=["admin"])
async def admin_command(message: types.Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "⛔ دسترسی ندارید."
        )

        return

    await message.answer(
        "👑 پنل مدیریت",
        reply_markup=admin_menu()
    )


@dp.message_handler(commands=["cancel"])
async def cancel_admin_state(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    admin_state.pop(ADMIN_ID, None)
    await message.answer("✅ عملیات لغو شد.")


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "admin_panel"
)
async def admin_panel(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    await call.message.edit_text(
        "👑 پنل مدیریت",
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# MANAGE ACCOUNTS
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "manage_accounts"
)
async def manage_accounts(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    keyboard = InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        InlineKeyboardButton(
            "➕ افزودن اکانت",
            callback_data="admin_add_account"
        ),
        InlineKeyboardButton(
            "📋 مدیریت / حذف / شارژ",
            callback_data="admin_list_accounts"
        ),
        InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="admin_panel"
        )
    )

    await call.message.edit_text(
        "🎁 مدیریت اکانت‌ها",
        reply_markup=keyboard
    )

    await call.answer()


# =========================================================
# ADD ACCOUNT START
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "admin_add_account"
)
async def admin_add_account(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    admin_state[ADMIN_ID] = {
        "step": "name"
    }

    await call.message.answer(
        "➕ افزودن اکانت\n\n"
        "1️⃣ نام اکانت را بفرست:"
    )

    await call.answer()


# =========================================================
# ADMIN TEXT INPUT
# =========================================================

@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID].get("step") in {
            "name", "description", "points", "stock", "login", "password"
        }
    ),
    content_types=types.ContentType.TEXT
)
async def admin_text(message: types.Message):

    if ADMIN_ID not in admin_state:
        return

    state = admin_state[ADMIN_ID]
    step = state["step"]

    # NAME

    if step == "name":

        state["name"] = message.text
        state["step"] = "description"

        await message.answer(
            "2️⃣ توضیحات اکانت را بفرست:"
        )

    # DESCRIPTION

    elif step == "description":

        state["description"] = message.text
        state["step"] = "points"

        await message.answer(
            "3️⃣ امتیاز لازم را به صورت عدد بفرست:\n\n"
            "مثلاً 100"
        )

    # POINTS

    elif step == "points":

        try:

            points = int(message.text)

            if points < 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ فقط یک عدد صحیح وارد کن."
            )

            return

        state["points"] = points
        state["step"] = "stock"

        await message.answer(
            "4️⃣ موجودی را وارد کن:\n\n"
            "مثلاً 5\n"
            "برای موجودی نامحدود بنویس: نامحدود"
        )

    # STOCK

    elif step == "stock":

        raw_stock = (message.text or "").strip().replace(",", "")
        if raw_stock in {"نامحدود", "بی نهایت", "بی‌نهایت", "unlimited", "∞"}:
            stock = -1
        else:
            try:
                stock = int(raw_stock)
                if stock < 0:
                    raise ValueError
            except ValueError:
                await message.answer(
                    "❌ فقط عدد صحیح وارد کن یا بنویس «نامحدود»."
                )
                return

        state["stock"] = stock
        state["step"] = "login"

        await message.answer(
            "5️⃣ ایمیل / Login اکانت را بفرست:"
        )

    # LOGIN

    elif step == "login":

        state["login"] = message.text
        state["step"] = "password"

        await message.answer(
            "6️⃣ رمز اکانت را بفرست:"
        )

    # PASSWORD

    elif step == "password":

        state["password"] = message.text
        state["step"] = "image"

        await message.answer(
            "7️⃣ حالا عکس اکانت را بفرست.\n\n"
            "اگر عکس نمی‌خواهی، بنویس:\n"
            "ندارد"
        )


# =========================================================
# ADMIN IMAGE INPUT
# =========================================================

@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID]["step"] == "image"
    ),
    content_types=types.ContentType.PHOTO
)
async def admin_image(message: types.Message):

    state = admin_state[ADMIN_ID]

    state["image_id"] = message.photo[-1].file_id

    save_account = True

    if save_account:

        cursor.execute("""
        INSERT INTO accounts
        (
            name,
            description,
            image_id,
            required_points,
            stock,
            login,
            password,
            active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            state["name"],
            state["description"],
            state["image_id"],
            state["points"],
            state["stock"],
            state["login"],
            state["password"]
        ))

        db.commit()

    del admin_state[ADMIN_ID]

    await message.answer(
        "✅ اکانت با موفقیت اضافه شد!\n\n"
        f"🎁 نام: {state['name']}\n"
        f"⭐ امتیاز: {state['points']}\n"
        f"📦 موجودی: {state['stock']}"
    )


# =========================================================
# ADMIN NO IMAGE
# =========================================================

@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID]["step"] == "image"
    ),
    content_types=types.ContentType.TEXT
)
async def admin_no_image(message: types.Message):

    if message.text.strip() != "ندارد":
        await message.answer(
            "❌ لطفاً عکس بفرست یا دقیقاً بنویس: ندارد"
        )

        return

    state = admin_state[ADMIN_ID]

    cursor.execute("""
    INSERT INTO accounts
    (
        name,
        description,
        image_id,
        required_points,
        stock,
        login,
        password,
        active
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        state["name"],
        state["description"],
        "",
        state["points"],
        state["stock"],
        state["login"],
        state["password"]
    ))

    db.commit()

    del admin_state[ADMIN_ID]

    await message.answer(
        "✅ اکانت بدون عکس ذخیره شد!\n\n"
        f"🎁 نام: {state['name']}\n"
        f"⭐ امتیاز: {state['points']}\n"
        f"📦 موجودی: {state['stock']}"
    )


# =========================================================
# ADMIN ACCOUNT LIST
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "admin_list_accounts"
)
async def admin_list_accounts(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    cursor.execute("""
    SELECT id, name, required_points, stock, active
    FROM accounts
    ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    if not rows:

        await call.message.edit_text(
            "📋 هنوز هیچ اکانتی ثبت نشده.",
            reply_markup=admin_menu()
        )

        await call.answer()

        return

    text = "📋 لیست اکانت‌ها\n\n"

    for account_id, name, points, stock, active in rows:
        status = "🟢 فعال" if active else "🔴 غیرفعال"
        text += (
            f"#{account_id} — {name}\n"
            f"⭐ {points} | 📦 {stock_text(stock)} | {status}\n\n"
        )

    keyboard = InlineKeyboardMarkup(row_width=1)
    for account_id, name, points, stock, active in rows:
        keyboard.add(
            InlineKeyboardButton(
                f"➕ شارژ {name}",
                callback_data=f"restock_account_{account_id}"
            ),
            InlineKeyboardButton(
                f"⭐ تغییر امتیاز {name}",
                callback_data=f"edit_points_{account_id}"
            ),
            InlineKeyboardButton(
                f"🗑 حذف {name}",
                callback_data=f"delete_account_{account_id}"
            )
        )
    keyboard.add(InlineKeyboardButton("🔙 پنل مدیریت", callback_data="admin_panel"))

    await call.message.edit_text(
        text + "\nاز دکمه‌های زیر برای شارژ یا حذف هر اکانت استفاده کن.",
        reply_markup=keyboard
    )

    await call.answer()


# =========================================================
# DELETE ACCOUNT
# =========================================================

@dp.callback_query_handler(lambda c: c.data.startswith("delete_account_"))
async def delete_account(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    try:
        account_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        await call.answer("❌ شناسه نامعتبر است.", show_alert=True)
        return

    cursor.execute("SELECT name FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        await call.answer("❌ اکانت پیدا نشد.", show_alert=True)
        return
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    db.commit()
    await call.answer(f"✅ اکانت «{row[0]}» حذف شد.", show_alert=True)
    await admin_list_accounts(call)


# =========================================================
# RESTOCK ACCOUNT
# =========================================================

@dp.callback_query_handler(lambda c: c.data.startswith("restock_account_"))
async def restock_account_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    try:
        account_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        await call.answer("❌ شناسه نامعتبر است.", show_alert=True)
        return

    cursor.execute("SELECT name, stock FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        await call.answer("❌ اکانت پیدا نشد.", show_alert=True)
        return

    admin_state[ADMIN_ID] = {"step": "restock_amount", "account_id": account_id}
    await call.message.answer(
        f"➕ شارژ موجودی: {row[0]}\n\n"
        f"موجودی فعلی: {stock_text(row[1])}\n"
        "تعداد اکانت جدید را به صورت عدد وارد کن.\n"
        "مثلاً: 10\n\n"
        "اگر می‌خواهی نامحدود شود، بنویس: نامحدود"
    )
    await call.answer()


@dp.message_handler(
    lambda m: (m.from_user.id == ADMIN_ID and ADMIN_ID in admin_state
               and admin_state[ADMIN_ID].get("step") == "restock_amount"),
    content_types=types.ContentType.TEXT
)
async def restock_amount(message: types.Message):
    state = admin_state[ADMIN_ID]
    raw = (message.text or "").strip().replace(",", "")
    if raw in {"نامحدود", "بی نهایت", "بی‌نهایت", "unlimited", "∞"}:
        new_stock = -1
        cursor.execute("UPDATE accounts SET stock = -1 WHERE id = ?", (state["account_id"],))
    else:
        try:
            amount = int(raw)
            if amount < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ فقط عدد صحیح وارد کن یا بنویس «نامحدود».")
            return
        cursor.execute("UPDATE accounts SET stock = CASE WHEN stock < 0 THEN -1 ELSE stock + ? END WHERE id = ?", (amount, state["account_id"]))
        new_stock = None

    db.commit()
    cursor.execute("SELECT name, stock FROM accounts WHERE id = ?", (state["account_id"],))
    row = cursor.fetchone()
    admin_state.pop(ADMIN_ID, None)
    if row:
        await message.answer(f"✅ موجودی «{row[0]}» با موفقیت شارژ شد.\n📦 موجودی جدید: {stock_text(row[1])}")
    else:
        await message.answer("❌ اکانت پیدا نشد.")


# =========================================================
# EDIT ACCOUNT REQUIRED POINTS
# =========================================================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_points_"))
async def edit_points_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    try:
        account_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        await call.answer("❌ شناسه نامعتبر است.", show_alert=True)
        return

    cursor.execute("SELECT name, required_points FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        await call.answer("❌ اکانت پیدا نشد.", show_alert=True)
        return

    admin_state[ADMIN_ID] = {"step": "edit_points", "account_id": account_id}
    await call.message.answer(
        f"⭐ تغییر امتیاز لازم برای «{row[0]}»\n\n"
        f"امتیاز فعلی: {row[1]}\n\n"
        "عدد جدید را وارد کن.\n"
        "مثلاً: 25"
    )
    await call.answer()


@dp.message_handler(
    lambda m: (m.from_user.id == ADMIN_ID and ADMIN_ID in admin_state
               and admin_state[ADMIN_ID].get("step") == "edit_points"),
    content_types=types.ContentType.TEXT
)
async def edit_points_save(message: types.Message):
    state = admin_state[ADMIN_ID]
    raw = (message.text or "").strip().replace(",", "")
    try:
        points = int(raw)
        if points < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ فقط یک عدد صحیح صفر یا بیشتر وارد کن.")
        return

    cursor.execute(
        "UPDATE accounts SET required_points = ? WHERE id = ?",
        (points, state["account_id"])
    )
    db.commit()

    cursor.execute("SELECT name FROM accounts WHERE id = ?", (state["account_id"],))
    row = cursor.fetchone()
    admin_state.pop(ADMIN_ID, None)

    if row:
        await message.answer(
            f"✅ امتیاز لازم «{row[0]}» تغییر کرد.\n"
            f"⭐ امتیاز جدید: {points}"
        )
    else:
        await message.answer("❌ اکانت پیدا نشد.")


# =========================================================
# MANAGE CHANNELS
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "manage_channels"
)
async def manage_channels(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    keyboard = InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        InlineKeyboardButton(
            "➕ افزودن کانال",
            callback_data="admin_add_channel"
        ),
        InlineKeyboardButton(
            "📋 لیست کانال‌ها",
            callback_data="admin_list_channels"
        ),
        InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="admin_panel"
        )
    )

    await call.message.edit_text(
        "📢 مدیریت جوین اجباری",
        reply_markup=keyboard
    )

    await call.answer()


# =========================================================
# ADD CHANNEL
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "admin_add_channel"
)
async def admin_add_channel(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    admin_state[ADMIN_ID] = {
        "step": "channel_id"
    }

    await call.message.answer(
        "➕ افزودن کانال\n\n"
        "Chat ID کانال را بفرست.\n\n"
        "مثلاً:\n"
        "-1001234567890"
    )

    await call.answer()


# =========================================================
# ADMIN CHANNEL INPUT
# =========================================================

@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID]["step"] == "channel_id"
    ),
    content_types=types.ContentType.TEXT
)
async def admin_channel_id(message: types.Message):
    raw = (message.text or '').strip()

    # قبول آیدی عددی کانال
    try:
        chat_id = int(raw)
    except (ValueError, TypeError):
        await message.answer(
            "❌ آیدی نامعتبر است. فقط Chat ID عددی بفرست.\n\n"
            "مثال: -1001234567890"
        )
        return

    if chat_id >= 0:
        await message.answer(
            "❌ Chat ID کانال باید منفی باشد و معمولاً با -100 شروع می‌شود.\n\n"
            "مثال: -1001234567890"
        )
        return

    state = admin_state[ADMIN_ID]
    state["chat_id"] = str(chat_id)

    # تلاش برای گرفتن نام کانال؛ اگر دسترسی نباشد، باز هم مرحله متوقف نمی‌شود.
    try:
        chat = await bot.get_chat(chat_id)
        state["auto_title"] = chat.title or "کانال"
        found_text = f"✅ آیدی کانال ثبت شد: {chat.title or 'بدون نام'}"
    except Exception as e:
        state["auto_title"] = "کانال"
        found_text = (
            "⚠️ آیدی ذخیره شد، ولی ربات نتوانست اطلاعات کانال را بگیرد.\n"
            "حتماً ربات را داخل کانال اضافه و ادمین کن؛ وگرنه بررسی عضویت کاربران کار نمی‌کند.\n\n"
            f"خطا: {type(e).__name__}"
        )

    state["step"] = "channel_title"
    await message.answer(
        found_text + "\n\n"
        "حالا نامی که می‌خواهی روی دکمه کانال نمایش داده شود را بفرست.\n"
        "اگر همان نام کانال را می‌خواهی، همان را بفرست."
    )


@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID]["step"] == "channel_title"
    ),
    content_types=types.ContentType.TEXT
)
async def admin_channel_title(message: types.Message):

    admin_state[ADMIN_ID]["title"] = message.text.strip()
    admin_state[ADMIN_ID]["step"] = "channel_link"

    await message.answer(
        "لینک دعوت کانال را بفرست:"
    )


@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID]["step"] == "channel_link"
    ),
    content_types=types.ContentType.TEXT
)
async def admin_channel_link(message: types.Message):

    state = admin_state[ADMIN_ID]

    cursor.execute("""
    INSERT INTO channels
    (chat_id, title, invite_link, active)
    VALUES (?, ?, ?, 1)
    """, (
        state["chat_id"],
        state["title"],
        message.text.strip()
    ))

    db.commit()

    del admin_state[ADMIN_ID]

    await message.answer(
        "✅ کانال با موفقیت به جوین اجباری اضافه شد."
    )


# =========================================================
# CHANNEL LIST
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "admin_list_channels"
)
async def admin_list_channels(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        await call.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    cursor.execute("""
    SELECT id, title, chat_id, active
    FROM channels
    ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    if not rows:

        await call.message.edit_text(
            "📋 هیچ کانالی ثبت نشده.",
            reply_markup=admin_menu()
        )

        await call.answer()

        return

    text = "📋 کانال‌های جوین اجباری\n\n"

    for channel_id, title, chat_id, active in rows:

        status = "🟢" if active else "🔴"

        text += (
            f"#{channel_id} {status} {title}\n"
            f"ID: {chat_id}\n\n"
        )

    keyboard = InlineKeyboardMarkup(row_width=1)

    for channel_id, title, chat_id, active in rows:
        keyboard.add(InlineKeyboardButton(
            f"🗑 حذف {title or chat_id}",
            callback_data=f"delete_channel_{channel_id}"
        ))

    keyboard.add(
        InlineKeyboardButton(
            "🔙 پنل مدیریت",
            callback_data="admin_panel"
        )
    )

    await call.message.edit_text(
        text,
        reply_markup=keyboard
    )

    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("delete_channel_"))
async def delete_channel(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    try:
        channel_id = int(call.data.split("_")[-1])
    except ValueError:
        await call.answer("❌ شناسه نامعتبر است.", show_alert=True)
        return

    cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    db.commit()
    await call.answer("✅ کانال حذف شد.", show_alert=True)
    await admin_list_channels(call)


# =========================================================
# PROFESSIONAL STATISTICS
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "statistics"
)
async def statistics(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    month_start = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    def one(query, params=()):
        cursor.execute(query, params)
        return cursor.fetchone()[0] or 0

    users = one("SELECT COUNT(*) FROM users")
    users_today = one("SELECT COUNT(*) FROM users WHERE substr(created_at,1,10)=?", (today,))
    users_7d = one("SELECT COUNT(*) FROM users WHERE created_at >= ?", (week_start,))
    users_30d = one("SELECT COUNT(*) FROM users WHERE created_at >= ?", (month_start,))

    total_points = one("SELECT SUM(points) FROM users")
    referrals = one("SELECT SUM(referrals) FROM users")
    users_with_points = one("SELECT COUNT(*) FROM users WHERE points > 0")

    total_accounts = one("SELECT COUNT(*) FROM accounts")
    active_accounts = one("SELECT COUNT(*) FROM accounts WHERE active=1")
    unlimited_accounts = one("SELECT COUNT(*) FROM accounts WHERE active=1 AND stock < 0")
    finite_stock = one("SELECT SUM(stock) FROM accounts WHERE active=1 AND stock >= 0")
    exhausted = one("SELECT COUNT(*) FROM accounts WHERE active=1 AND stock=0")

    total_deliveries = one("SELECT COUNT(*) FROM deliveries")
    deliveries_today = one("SELECT COUNT(*) FROM deliveries WHERE substr(delivered_at,1,10)=?", (today,))
    deliveries_7d = one("SELECT COUNT(*) FROM deliveries WHERE delivered_at >= ?", (week_start,))
    deliveries_30d = one("SELECT COUNT(*) FROM deliveries WHERE delivered_at >= ?", (month_start,))
    spent_total = one("SELECT SUM(points_spent) FROM deliveries")
    spent_today = one("SELECT SUM(points_spent) FROM deliveries WHERE substr(delivered_at,1,10)=?", (today,))

    channels = one("SELECT COUNT(*) FROM channels WHERE active=1")

    # Most requested accounts
    cursor.execute("""
        SELECT a.name, COUNT(d.id) AS cnt
        FROM deliveries d
        LEFT JOIN accounts a ON a.id=d.account_id
        GROUP BY d.account_id
        ORDER BY cnt DESC
        LIMIT 3
    """)
    top_accounts = cursor.fetchall()

    top_text = ""
    if top_accounts:
        top_text = "\n🏆 پرفروش‌ترین اکانت‌ها\n" + "\n".join(
            f"• {name or 'حذف‌شده'}: {cnt} تحویل" for name, cnt in top_accounts
        )

    text = (
        "📊 آمار حرفه‌ای ربات\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 کل کاربران: {users}\n"
        f"🆕 کاربران امروز: {users_today}\n"
        f"📅 کاربران ۷ روز اخیر: {users_7d}\n"
        f"🗓 کاربران ۳۰ روز اخیر: {users_30d}\n"
        f"⭐ مجموع امتیاز موجود: {total_points}\n"
        f"💎 کاربران دارای امتیاز: {users_with_points}\n"
        f"👥 مجموع دعوت موفق: {referrals}\n\n"
        "🎁 وضعیت اکانت‌ها\n"
        f"📦 کل اکانت‌ها: {total_accounts}\n"
        f"🟢 اکانت‌های فعال: {active_accounts}\n"
        f"📉 موجودی عددی: {finite_stock}\n"
        f"♾️ اکانت‌های نامحدود: {unlimited_accounts}\n"
        f"⛔ اکانت‌های تمام‌شده: {exhausted}\n\n"
        "🎉 تحویل اکانت\n"
        f"📤 کل تحویل‌ها: {total_deliveries}\n"
        f"🔥 تحویل امروز: {deliveries_today}\n"
        f"📅 تحویل ۷ روز اخیر: {deliveries_7d}\n"
        f"🗓 تحویل ۳۰ روز اخیر: {deliveries_30d}\n"
        f"⭐ امتیاز خرج‌شده: {spent_total}\n"
        f"💸 خرج‌شده امروز: {spent_today}\n\n"
        "📢 جوین اجباری\n"
        f"📣 کانال‌های فعال: {channels}"
        f"{top_text}"
    )

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer("✅ آمار به‌روز شد.")


# =========================================================
# RESET STATISTICS
# =========================================================

@dp.callback_query_handler(lambda c: c.data == "reset_statistics")
async def reset_statistics(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ بله، ریست کن", callback_data="confirm_reset_statistics"),
        InlineKeyboardButton("❌ انصراف", callback_data="statistics")
    )

    await call.message.edit_text(
        "⚠️ ریست آمار\n\n"
        "با تأیید، امتیاز و تعداد دعوت کاربران صفر می‌شود و تاریخچه تحویل‌ها پاک می‌شود.\n"
        "لیست کاربران و اکانت‌ها حذف نمی‌شوند.",
        reply_markup=keyboard
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "confirm_reset_statistics")
async def confirm_reset_statistics(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    cursor.execute("UPDATE users SET points = 0, referrals = 0")
    cursor.execute("DELETE FROM deliveries")
    db.commit()

    await call.answer("✅ آمار با موفقیت ریست شد.", show_alert=True)
    await statistics(call)


# =========================================================
# BROADCAST
# =========================================================

@dp.callback_query_handler(lambda c: c.data == "broadcast")
async def broadcast_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    admin_state[ADMIN_ID] = {"step": "broadcast"}
    await call.message.answer(
        "📣 ارسال پیام همگانی\n\n"
        "متنی که می‌خواهی برای همه کاربران ثبت‌شده ارسال شود را بفرست.\n\n"
        "برای لغو /cancel را بزن."
    )
    await call.answer()


@dp.message_handler(
    lambda m: (m.from_user.id == ADMIN_ID and ADMIN_ID in admin_state
               and admin_state[ADMIN_ID].get("step") == "broadcast"),
    content_types=types.ContentType.TEXT
)
async def broadcast_send(message: types.Message):
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ پیام خالی است.")
        return

    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]

    success = 0
    failed = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            success += 1
        except Exception:
            failed += 1

    admin_state.pop(ADMIN_ID, None)
    await message.answer(
        "✅ ارسال همگانی تمام شد.\n\n"
        f"👥 کل کاربران: {len(user_ids)}\n"
        f"✅ ارسال موفق: {success}\n"
        f"❌ ناموفق: {failed}"
    )


# =========================================================
# CHANNEL BROADCAST
# =========================================================

@dp.callback_query_handler(lambda c: c.data == "channel_broadcast")
async def channel_broadcast_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    cursor.execute("""
        SELECT id, title, chat_id
        FROM channels
        WHERE active = 1
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()

    if not rows:
        await call.answer("❌ هیچ کانال فعالی ثبت نشده است.", show_alert=True)
        return

    admin_state[ADMIN_ID] = {
        "step": "channel_broadcast_select",
        "channel_ids": []
    }

    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel_id, title, chat_id in rows:
        keyboard.add(
            InlineKeyboardButton(
                f"☐ {title or chat_id}",
                callback_data=f"cbch_{channel_id}"
            )
        )

    keyboard.add(
        InlineKeyboardButton("📨 ارسال به کانال‌های انتخاب‌شده", callback_data="cbch_done"),
        InlineKeyboardButton("❌ لغو", callback_data="admin_panel")
    )

    await call.message.edit_text(
        "📢 ارسال پیام به کانال‌ها\n\n"
        "کانال‌هایی که می‌خواهی پیام در آن‌ها منتشر شود را انتخاب کن:\n"
        "با زدن روی هر کانال، انتخاب/لغو انتخاب می‌شود.",
        reply_markup=keyboard
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("cbch_"))
async def channel_broadcast_select(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    state = admin_state.get(ADMIN_ID)
    if not state or state.get("step") != "channel_broadcast_select":
        await call.answer("❌ این عملیات منقضی شده است.", show_alert=True)
        return

    if call.data == "cbch_done":
        selected = state.get("channel_ids", [])
        if not selected:
            await call.answer("❌ حداقل یک کانال را انتخاب کن.", show_alert=True)
            return

        state["step"] = "channel_broadcast_content"
        await call.message.edit_text(
            "📝 حالا پیام را بفرست.\n\n"
            "• برای متن ساده: متن را ارسال کن.\n"
            "• برای عکس + متن: عکس را با کپشن ارسال کن.\n\n"
            "برای لغو /cancel را بزن."
        )
        await call.answer()
        return

    try:
        channel_id = int(call.data.split("_")[-1])
    except ValueError:
        await call.answer("❌ شناسه نامعتبر است.", show_alert=True)
        return

    selected = state.setdefault("channel_ids", [])
    if channel_id in selected:
        selected.remove(channel_id)
        selected_text = "☐"
        result = "❌ از انتخاب خارج شد."
    else:
        selected.append(channel_id)
        selected_text = "☑"
        result = "✅ انتخاب شد."

    cursor.execute("""
        SELECT id, title, chat_id
        FROM channels
        WHERE active = 1
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()

    keyboard = InlineKeyboardMarkup(row_width=1)
    for row_id, title, chat_id in rows:
        mark = "☑" if row_id in selected else "☐"
        keyboard.add(
            InlineKeyboardButton(
                f"{mark} {title or chat_id}",
                callback_data=f"cbch_{row_id}"
            )
        )

    keyboard.add(
        InlineKeyboardButton("📨 ارسال به کانال‌های انتخاب‌شده", callback_data="cbch_done"),
        InlineKeyboardButton("❌ لغو", callback_data="admin_panel")
    )

    await call.message.edit_reply_markup(reply_markup=keyboard)
    await call.answer(result)


@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and admin_state[ADMIN_ID].get("step") == "channel_broadcast_content"
    ),
    content_types=[types.ContentType.TEXT, types.ContentType.PHOTO]
)
async def channel_broadcast_send(message: types.Message):
    state = admin_state.get(ADMIN_ID)
    if not state:
        return

    selected_ids = state.get("channel_ids", [])
    if not selected_ids:
        admin_state.pop(ADMIN_ID, None)
        await message.answer("❌ هیچ کانالی انتخاب نشده است.")
        return

    if message.content_type == types.ContentType.PHOTO:
        photo_id = message.photo[-1].file_id
        caption = (message.caption or "").strip()

        if not caption:
            await message.answer("❌ برای عکس، متن را در قسمت کپشن عکس وارد کن.")
            return

        send_method = "photo"
    else:
        text = (message.text or "").strip()
        if not text:
            await message.answer("❌ پیام خالی است.")
            return

        send_method = "text"

    success = 0
    failed = 0
    failed_channels = []

    for channel_id in selected_ids:
        cursor.execute(
            "SELECT title, chat_id FROM channels WHERE id = ? AND active = 1",
            (channel_id,)
        )
        row = cursor.fetchone()
        if not row:
            failed += 1
            continue

        title, chat_id = row
        try:
            if send_method == "photo":
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_id,
                    caption=caption
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text
                )
            success += 1
        except Exception:
            failed += 1
            failed_channels.append(title or chat_id)

    admin_state.pop(ADMIN_ID, None)

    result = (
        "✅ ارسال به کانال‌ها تمام شد.\n\n"
        f"📢 کانال‌های انتخاب‌شده: {len(selected_ids)}\n"
        f"✅ ارسال موفق: {success}\n"
        f"❌ ناموفق: {failed}"
    )

    if failed_channels:
        result += "\n\n⚠️ کانال‌های ناموفق:\n" + "\n".join(
            f"• {name}" for name in failed_channels
        )

    await message.answer(result)


# =========================================================
# BACK MAIN
# =========================================================

@dp.callback_query_handler(
    lambda c: c.data == "back_main"
)
async def back_main(call: types.CallbackQuery):

    await call.message.edit_text(
        "🏠 منوی اصلی",
        reply_markup=main_menu(call.from_user.id)
    )

    await call.answer()


# =========================================================
# START POLLING
# =========================================================

if __name__ == "__main__":

    print("🤖 Bot is running...")

    executor.start_polling(
        dp,
        skip_updates=False
    )
