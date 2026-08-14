import { Bot, InputFile } from 'grammy';
import fs from 'node:fs/promises';
import { config } from './config.js';
import { authMiddleware } from './middlewares/auth.js';
import { downloadMedia } from './services/downloader.js';
import { calculateSha256 } from './utils/crypto.js';

const bot = new Bot(config.botToken);

bot.use(authMiddleware);

bot.command('start', async (ctx) => {
  await ctx.reply('SYSTEM READY. Send URL to fetch media.');
});

bot.command('ping', async (ctx) => {
  const ping = Date.now() - ctx.message.date * 1000;
  await ctx.reply(`PONG: ${ping >= 0 ? ping : 0}ms`);
});

// Обработка текстовых ссылок
bot.on('message:text', async (ctx) => {
  const text = ctx.message.text.trim();
  
  if (!text.startsWith('http://') && !text.startsWith('https://')) {
    return;
  }

  const statusMsg = await ctx.reply('[1/3] Fetching stream & muxing tracks...');
  let downloadedFilePath = null;

  try {
    const meta = await downloadMedia(text);
    downloadedFilePath = meta.filePath;

    await ctx.api.editMessageText(ctx.chat.id, statusMsg.message_id, '[2/3] Computing SHA-256 checksum...');

    const fileStat = await fs.stat(downloadedFilePath);
    const sha256 = await calculateSha256(downloadedFilePath);
    const sizeMb = (fileStat.size / (1024 * 1024)).toFixed(2);

    // Проверка лимита Telegram Bot API (50 MB)
    if (fileStat.size > 50 * 1024 * 1024) {
      await ctx.api.editMessageText(
        ctx.chat.id,
        statusMsg.message_id,
        `[ERROR] File size (${sizeMb} MB) exceeds standard Telegram Bot API 50 MB limit.\nLocal Bot API Server is required.`
      );
      return;
    }

    await ctx.api.editMessageText(ctx.chat.id, statusMsg.message_id, '[3/3] Uploading raw document...');

    // Формируем техническую карточку
    const caption = [
      `TITLE: ${meta.title}`,
      `SOURCE: ${meta.extractor} (@${meta.uploader})`,
      `FORMAT: ${meta.resolution} @ ${meta.fps}fps (${meta.vcodec} / ${meta.acodec})`,
      `DURATION: ${meta.duration}s | SIZE: ${sizeMb} MB`,
      `SHA256: <code>${sha256}</code>`,
    ].join('\n');

    // Отправка без сжатия
    await ctx.replyWithDocument(new InputFile(downloadedFilePath, `${meta.title.slice(0, 40)}.mp4`), {
      caption,
      parse_mode: 'HTML',
    });

    // Удаляем статусное сообщение после успешной выгрузки
    await ctx.api.deleteMessage(ctx.chat.id, statusMsg.message_id);
  } catch (error) {
    console.error('[EXEC ERROR]', error);
    await ctx.api.editMessageText(
      ctx.chat.id,
      statusMsg.message_id,
      `[FAIL] ${error.message}`
    );
  } finally {
    if (downloadedFilePath) {
      await fs.unlink(downloadedFilePath).catch(() => {});
    }
  }
});

bot.catch((err) => {
  console.error('[FATAL]', err);
});

const stopHandler = () => {
  bot.stop();
  process.exit(0);
};

process.once('SIGINT', stopHandler);
process.once('SIGTERM', stopHandler);

bot.start({
  onStart: (info) => console.log(`[ONLINE] @${info.username}`),
});