import 'dotenv/config';

if (!process.env.BOT_TOKEN) {
  console.error('❌ Ошибка: Переменная BOT_TOKEN не задана в .env');
  process.exit(1);
}

// Преобразуем строку с ID (например, "111,222") в массив чисел
const allowedUserIds = (process.env.ALLOWED_USER_IDS || '')
  .split(',')
  .map((id) => Number(id.trim()))
  .filter((id) => !isNaN(id) && id > 0);

if (allowedUserIds.length === 0) {
  console.warn('⚠️ Внимание: ALLOWED_USER_IDS пуст. Бот будет игнорировать всех!');
}

export const config = {
  botToken: process.env.BOT_TOKEN,
  allowedUserIds,
};  