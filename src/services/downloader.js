import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { config } from '../config.js';

export async function downloadMedia(url) {
  const downloadDir = path.resolve('downloads');
  await fs.mkdir(downloadDir, { recursive: true }); // Гарантируем наличие папки

  const tempId = `media_${Date.now()}`;
  const outputTemplate = path.join(downloadDir, `${tempId}.%(ext)s`);

  const args = [
    '--no-playlist',
    '--no-warnings',
    '--no-simulate',      // Важно: отключает симуляцию и принудительно качает файл
    '--dump-json',        // Возвращает метаданные в stdout
    '-f', 'bv*+ba/b',     // Максимальное качество видео и звука
    '--merge-output-format', 'mp4',
    '-o', outputTemplate,
  ];

  if (config.proxyUrl) {
    args.push('--proxy', config.proxyUrl);
  }

  if (config.cookiesFile && existsSync(config.cookiesFile)) {
    args.push('--cookies', path.resolve(config.cookiesFile));
  }

  args.push('--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36');
  args.push(url);

  return new Promise((resolve, reject) => {
    const proc = spawn('yt-dlp', args);

    let stdoutData = '';
    let stderrData = '';

    proc.stdout.on('data', (data) => {
      stdoutData += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderrData += data.toString();
    });

    proc.on('close', async (code) => {
      if (code !== 0) {
        return reject(new Error(stderrData.trim() || `yt-dlp exited with code ${code}`));
      }

      try {
        // Берем последнюю валидную JSON строку из вывода
        const jsonLines = stdoutData.trim().split('\n').filter(Boolean);
        const metadata = JSON.parse(jsonLines[jsonLines.length - 1]);
        
        const finalPath = path.join(downloadDir, `${tempId}.mp4`);

        // Ждем физического появления файла
        await fs.access(finalPath);

        resolve({
          filePath: finalPath,
          title: metadata.title || 'Untitled',
          uploader: metadata.uploader || metadata.channel || metadata.creator || 'Unknown',
          duration: metadata.duration || 0,
          resolution: metadata.resolution || (metadata.width && metadata.height ? `${metadata.width}x${metadata.height}` : 'N/A'),
          vcodec: metadata.vcodec || 'unknown',
          acodec: metadata.acodec || 'unknown',
          fps: metadata.fps || 'N/A',
          extractor: metadata.extractor_key || 'Generic',
        });
      } catch (err) {
        reject(new Error(`Failed to parse yt-dlp output or locate file: ${err.message}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to start yt-dlp process: ${err.message}`));
    });
  });
}