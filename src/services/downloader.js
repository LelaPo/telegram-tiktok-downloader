import { spawn, execFile } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { promisify } from 'node:util';
import { config } from '../config.js';

const execFilePromise = promisify(execFile);

// Получение реального FPS и разрешения через ffprobe
async function getStreamInfo(filePath) {
  try {
    const { stdout } = await execFilePromise('ffprobe', [
      '-v', 'error',
      '-select_streams', 'v:0',
      '-show_entries', 'stream=r_frame_rate,width,height,codec_name',
      '-of', 'json',
      filePath,
    ]);
    const info = JSON.parse(stdout);
    const stream = info.streams?.[0];
    if (!stream) return { fps: 'N/A', resolution: null, vcodec: null };

    let fps = 'N/A';
    if (stream.r_frame_rate) {
      const [num, den] = stream.r_frame_rate.split('/').map(Number);
      if (den > 0) fps = Math.round(num / den);
    }

    return {
      fps,
      resolution: stream.width && stream.height ? `${stream.width}x${stream.height}` : null,
      vcodec: stream.codec_name || null,
    };
  } catch {
    return { fps: 'N/A', resolution: null, vcodec: null };
  }
}

export async function downloadMedia(url) {
  const downloadDir = path.resolve('downloads');
  await fs.mkdir(downloadDir, { recursive: true });

  const tempId = `media_${Date.now()}`;
  const outputTemplate = path.join(downloadDir, `${tempId}.%(ext)s`);

  const args = [
    '--no-playlist',
    '--no-warnings',
    '--no-simulate',
    '--dump-json',
    '-f', 'bv*+ba/b',
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

    proc.stdout.on('data', (data) => (stdoutData += data.toString()));
    proc.stderr.on('data', (data) => (stderrData += data.toString()));

    proc.on('close', async (code) => {
      if (code !== 0) {
        return reject(new Error(stderrData.trim() || `yt-dlp exited with code ${code}`));
      }

      try {
        const jsonLines = stdoutData.trim().split('\n').filter(Boolean);
        const metadata = JSON.parse(jsonLines[jsonLines.length - 1]);
        const finalPath = path.join(downloadDir, `${tempId}.mp4`);

        await fs.access(finalPath);

        // Достаем точные данные видеопотока через ffprobe
        const probe = await getStreamInfo(finalPath);

        resolve({
          filePath: finalPath,
          title: metadata.title || 'Untitled',
          uploader: metadata.uploader || metadata.channel || metadata.creator || 'Unknown',
          duration: metadata.duration || 0,
          resolution: probe.resolution || metadata.resolution || 'N/A',
          vcodec: probe.vcodec || metadata.vcodec || 'unknown',
          acodec: metadata.acodec || 'unknown',
          fps: probe.fps !== 'N/A' ? probe.fps : (metadata.fps || 'N/A'),
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