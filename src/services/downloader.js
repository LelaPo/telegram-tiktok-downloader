import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs/promises';

export async function downloadMedia(url) {
  const downloadDir = path.resolve('downloads');
  const tempId = `media_${Date.now()}`;
  const outputTemplate = path.join(downloadDir, `${tempId}.%(ext)s`);

  // Аргументы для максимального качества видео и звука
  const args = [
    '--no-playlist',
    '--no-warnings',
    '-f', 'bv*+ba/b',
    '--merge-output-format', 'mp4',
    '--dump-single-json', // Возвращает JSON-метаданные в stdout
    '-o', outputTemplate,
    url,
  ];

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
        const metadata = JSON.parse(stdoutData);
        const finalPath = path.join(downloadDir, `${tempId}.mp4`);

        // Проверяем существование результирующего файла
        await fs.access(finalPath);

        resolve({
          filePath: finalPath,
          title: metadata.title || 'Untitled',
          uploader: metadata.uploader || metadata.channel || 'Unknown',
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