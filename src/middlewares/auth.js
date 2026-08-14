import { config } from '../config.js';

export async function authMiddleware(ctx, next) {
  const userId = ctx.from?.id;

  if (!userId || !config.allowedUserIds.includes(userId)) {
    console.warn(`[AUTH] Попытка доступа от неавторизованного пользователя: ID ${userId} (@${ctx.from?.username || 'no_username'})`);
    return; // Ничего не отвечаем
  }

  await next();
}