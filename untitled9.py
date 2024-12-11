from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import logging
import os

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
user_state = {}  # Har bir foydalanuvchining holati saqlanadi


# Dummy database (odatda real bazada saqlash kerak)
DATABASE = {
    "users": {},
    "tests": {},
    "scores": {}
}

# Start command
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    DATABASE["users"].setdefault(user.id, {"nickname": user.username, "tests_created": 0})
    message = (
        "\U0001F44B Xush kelibsiz!\n"
        "\nBot orqali quizz tuzish va boshqalarning testlarini yechishingiz mumkin.\n"
        "\nBuyruqlar:\n"
        "/create - Yangi test yaratish\n"
        "/tests - Mavjud testlarni yechish\n"
        "/score - Reytingingizni ko'rish\n"
        "/stats - Kim qancha test tuzganini ko'rish\n"
        "/edit_test - Yaratgan testlaringizni tahrirlash\n"
        "/delete_test - (Tez orada) Yaratgan testlaringizni o'chirish\n"
    )
    update.message.reply_text(message)
# Create test command
def create(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    DATABASE["users"].setdefault(user_id, {"nickname": update.effective_user.username, "tests_created": 0})
    context.user_data["creating_test"] = {}

    keyboard = [
        [InlineKeyboardButton("Matematika", callback_data="subject_Matematika")],
        [InlineKeyboardButton("Geografiya", callback_data="subject_Geografiya")],
        [InlineKeyboardButton("Tarix", callback_data="subject_Tarix")],
        [InlineKeyboardButton("Biologiya", callback_data="subject_Biologiya")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("Qaysi fanga oid test tuzmoqchisiz? Tugmalardan birini tanlang:", reply_markup=reply_markup)

# Handle subject selection
def handle_subject_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    subject = query.data.split("_")[1]

    context.user_data["creating_test"] = {
        "subject": subject,
        "questions": []
    }
    query.edit_message_text(f"{subject} fani uchun test yaratmoqdasiz. Birinchi savolni kiriting:")

# Handle messages for test creation
def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if "creating_test" in context.user_data:
        if not context.user_data["creating_test"].get("current_question"):
            context.user_data["creating_test"]["current_question"] = {
                "question": update.message.text,
                "options": []
            }
            update.message.reply_text("Savol qabul qilindi! Endi A, B, C variantlarni kiriting.")
        else:
            current_question = context.user_data["creating_test"]["current_question"]

            if len(current_question["options"]) < 3:
                if update.message.text.startswith(("A-", "B-", "C-")):
                    current_question["options"].append(update.message.text.split("-", 1)[1].strip())
                    if len(current_question["options"]) < 3:
                        next_option = ["B", "C"][len(current_question["options"]) - 1]
                        update.message.reply_text(f"{next_option}-variantni kiriting:")
                    else:
                        update.message.reply_text("Variantlar qabul qilindi. To'g'ri javob raqamini kiriting (1, 2 yoki 3):")
                else:
                    update.message.reply_text("Iltimos, variantlarni A-, B-, C- formatida kiriting.")
            else:
                try:
                    correct_option = int(update.message.text)
                    if 1 <= correct_option <= 3:
                        current_question["correct_option"] = correct_option
                        context.user_data["creating_test"]["questions"].append(current_question)
                        context.user_data["creating_test"].pop("current_question")
                        update.message.reply_text("To'g'ri javob qabul qilindi. Keyingi savolni kiriting yoki /finish ni bosing.")
                    else:
                        raise ValueError
                except ValueError:
                    update.message.reply_text("Iltimos, to'g'ri javob raqamini (1, 2 yoki 3) kiriting.")
    else:
        update.message.reply_text("Buyruqni to'g'ri kiriting yoki /start ni bosing.")
def tests(update: Update, context: CallbackContext):
    if not DATABASE["tests"]:
        update.message.reply_text("Hozircha mavjud testlar yo'q.")
        return

    keyboard = []
    for test_id, test in DATABASE["tests"].items():
        author_name = DATABASE["users"].get(test["author"], {}).get("nickname", "Noma'lum")
        keyboard.append([InlineKeyboardButton(f"{test['subject']} (Muallif: {author_name})", callback_data=f"test_{test_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Mavjud testlardan birini tanlang:", reply_markup=reply_markup)
# Finish creating test
# Start solving a test
def solve_test(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    test_id = int(query.data.split('_')[1])
    test = DATABASE["tests"].get(test_id)

    if not test:
        query.edit_message_text("Ushbu test topilmadi.")
        return

    context.user_data["solving_test"] = {
        "test_id": test_id,
        "current_question": 0,
        "score": 0
    }

    send_question(query.message, test, 0)
 
def finish(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if "creating_test" in context.user_data:
        test = context.user_data.pop("creating_test")
        test_id = len(DATABASE["tests"]) + 1
        DATABASE["tests"][test_id] = {
            "author": user_id,
            "subject": test["subject"],
            "questions": test["questions"]
        }
        DATABASE["users"][user_id]["tests_created"] += 1

        update.message.reply_text(f"Test muvaffaqiyatli saqlandi! ID: {test_id}")
    else:
        update.message.reply_text("Siz test yaratmayapsiz. /create ni bosing.")

# Score command
def score(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_score = DATABASE["scores"].get(user_id, 0)
    update.message.reply_text(f"Sizning umumiy balingiz: {user_score}")

# Stats command
def stats(update: Update, context: CallbackContext):
    stats_message = "Test yaratgan foydalanuvchilar:\n\n"
    for user_id, user_data in DATABASE["users"].items():
        stats_message += f"{user_data['nickname']}: {user_data['tests_created']} ta test\n"
    update.message.reply_text(stats_message)
def handle_answer(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_data = context.user_data.get("solving_test")
    if not user_data:
        query.edit_message_text("Siz hozir test yechmayapsiz.")
        return

    test_id = user_data["test_id"]
    test = DATABASE["tests"].get(test_id)
    question_index = user_data["current_question"]
    question = test["questions"][question_index]
    selected_option = int(query.data.split('_')[1])
    if selected_option == question["correct_option"]:
        user_data["score"] += 10

    if question_index + 1 < len(test["questions"]):
        user_data["current_question"] += 1
        send_question(query.message, test, user_data["current_question"])
    else:
        finalize_test(query.message, test, user_data, update.effective_user.id, context)
        context.user_data.pop("solving_test")    
def send_question(message, test, question_index):
    question = test["questions"][question_index]
    keyboard = [
        [InlineKeyboardButton(option, callback_data=f"answer_{i+1}")]
        for i, option in enumerate(question["options"])
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message.reply_text(f"Savol: {question['question']}", reply_markup=reply_markup)        
    
def finalize_test(message, test, user_data, user_id, context):
    score = user_data["score"]
    author_id = test["author"]
    author_name = DATABASE["users"].get(author_id, {}).get("nickname", "Noma'lum")
    user_name = DATABASE["users"].get(user_id, {}).get("nickname", "Noma'lum")

    # Test yechgan foydalanuvchiga natijani ko‘rsatish
    message.reply_text(f"Test yakunlandi! Umumiy ball: {score}")

    # Test muallifiga xabar yuborish
    if score > 0:  # Faqat ball olgan bo‘lsa xabar yuboramiz
        author_message = (
            f"Foydalanuvchi @{user_name} sizning '{test['subject']}' fani testingizdan {score} ball to‘pladi!"
        )
        try:
            context.bot.send_message(chat_id=author_id, text=author_message)
        except Exception as e:
            logging.warning(f"Muallifga xabar yuborishda xato yuz berdi: {e}")
# Testni tahrirlash uchun /edit_test komandasi
def edit_test(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_tests = {test_id: test for test_id, test in DATABASE["tests"].items() if test["author"] == user_id}

    if not user_tests:
        update.message.reply_text("Siz hali birorta test yaratmagansiz.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{test['subject']} (ID: {test_id})", callback_data=f"edit_{test_id}")]
        for test_id, test in user_tests.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Tahrirlash uchun testni tanlang:", reply_markup=reply_markup)
def handle_edit_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    test_id = int(query.data.split('_')[1])
    test = DATABASE["tests"].get(test_id)

    if not test:
        query.edit_message_text("Ushbu test topilmadi.")
        return

    context.user_data["editing_test"] = {
        "test_id": test_id,
        "current_question": 0
    }

    # To'g'ri indentatsiya (bir xil darajada bo'lishi kerak)
    send_edit_question(query.message, test, 0)

def handle_edit_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    test_id = int(query.data.split('_')[1])
    test = DATABASE["tests"].get(test_id)

    if not test:
        query.edit_message_text("Ushbu test topilmadi.")
        return

    context.user_data["editing_test"] = {
        "test_id": test_id,
        "current_question": 0
    }

    send_edit_question(query.message, test, 0)
def send_edit_question(message, test, question_index):
    question = test["questions"][question_index]
    message.reply_text(
        f"Savol: {question['question']}\n"
        f"A: {question['options'][0]}\n"
        f"B: {question['options'][1]}\n"
        f"C: {question['options'][2]}\n"
        f"To'g'ri javob: {question['correct_option']}\n\n"
        "Yangi savolni kiriting yoki /skip ni bosing (o'zgartirmaslik uchun):"
    )
def skip_command(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Foydalanuvchi testda ekanligini tekshiramiz
    if 'current_test' in user_data and 'current_question' in user_data:
        # Savollarni o'tkazib yuborish
        user_data['current_question'] += 1
        send_next_question(update, context)
    else:
        # Testda bo'lmasa
        update.message.reply_text("Hozir hech qanday test jarayonida emassiz.")

def send_next_question(update: Update, context: CallbackContext):
    user_data = context.user_data
    test = user_data.get('current_test')
    question_index = user_data.get('current_question', 0)

    if test and question_index < len(test['questions']):
        question = test['questions'][question_index]
        update.message.reply_text(f"{question_index + 1}. {question['text']}")
    else:
        update.message.reply_text("Test yakunlandi. /finish komandasi bilan yakunlang.")

    
def handle_edit_message(update: Update, context: CallbackContext):
    user_data = context.user_data.get("editing_test")
    if not user_data:
        update.message.reply_text("Siz hozir test tahrirlamayapsiz.")
        return

    test_id = user_data["test_id"]
    question_index = user_data["current_question"]
    test = DATABASE["tests"].get(test_id)

    if not test:
        update.message.reply_text("Xatolik yuz berdi. Test topilmadi.")
        return

    test["questions"][question_index]["question"] = update.message.text
    update.message.reply_text("Savol o'zgartirildi! Variantlarni kiriting yoki /skip ni bosing.")

# Testni o'chirish uchun /delete_test komandasi
def delete_test(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    # Foydalanuvchining yaratgan testlarini topamiz
    user_tests = {
        test_id: test for test_id, test in DATABASE["tests"].items() if test["author"] == user_id
    }

    if not user_tests:
        update.message.reply_text("Siz yaratgan testlar mavjud emas.")
        return

    # Foydalanuvchining testlarini tugmalar ko'rinishida taklif qilamiz
    keyboard = [
        [InlineKeyboardButton(f"{test['subject']} (ID: {test_id})", callback_data=f"delete_{test_id}")]
        for test_id, test in user_tests.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("O'chirish uchun testni tanlang:", reply_markup=reply_markup)

# CallbackQueryHandler orqali testni tahrirlash va o'chirishni amalga oshirish
def handle_edit_or_delete(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    data = query.data.split('_')
    action, test_id = data[0], int(data[1])

    test = DATABASE["tests"].get(test_id)
    if not test:
        query.edit_message_text("Test topilmadi.")
        return

    user_id = update.effective_user.id
    if test["author"] != user_id:
        query.edit_message_text("Siz bu testni tahrirlash yoki o'chirish huquqiga ega emassiz.")
        return

    if action == "edit":
        query.edit_message_text("Hozircha tahrirlash funksiyasi qo'shilmagan.")
        # Bu yerga keyingi bosqichda tahrirlash uchun kod qo'shamiz
    elif action == "delete":
        del DATABASE["tests"][test_id]
        query.edit_message_text("Test muvaffaqiyatli o'chirildi.")

# Command handlerlarni qo'shish
def main():
    token = ("7611051463:AAGXjtF-LswOf4p2O9LCtaSx96jdFnKD-WQ")  # Tokenni muhit o'zgaruvchisidan oling
    if not token:
        raise ValueError("Telegram token o'rnatilmagan.")

    updater = Updater(token, use_context=True)
    

    dp = updater.dispatcher
 

# Command Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("create", create))
    dp.add_handler(CommandHandler("tests", tests))
    dp.add_handler(CommandHandler("finish", finish))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("score", score))
    dp.add_handler(CommandHandler("skip", skip_command))

    

# CallbackQueryHandlers
    dp.add_handler(CallbackQueryHandler(handle_edit_selection, pattern="edit_"))
    dp.add_handler(CallbackQueryHandler(handle_subject_selection, pattern="subject_"))
    dp.add_handler(CallbackQueryHandler(solve_test, pattern="test_"))
    dp.add_handler(CallbackQueryHandler(handle_answer, pattern="answer_"))

# Message Handlers
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_edit_message))
    

# Error dp.add_error_handler(error_handler)
    
    

# Start polling
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
