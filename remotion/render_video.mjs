import { bundle } from '@remotion/bundler';
import { selectComposition, renderMedia } from '@remotion/renderer';
import { readFileSync } from 'fs';
import { resolve, join, dirname, basename } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main() {
  console.log('1. 读取渲染数据...');
  const inputData = JSON.parse(readFileSync(join(__dirname, 'input.json'), 'utf-8'));
  console.log('   标题:', inputData.title?.substring(0, 40));
  console.log('   分镜:', inputData.segments?.length, '段');

  // 不再转base64！改用staticFile路径（相对于remotion/public/）
  // 图片路径：data/projects/.../img_01.jpg -> images/img_01.jpg
  for (const seg of inputData.segments) {
    if (seg.image && !seg.image.startsWith('data:')) {
      seg.image = `images/${basename(seg.image)}`;
    }
  }
  if (inputData.coverImage && !inputData.coverImage.startsWith('data:')) {
    inputData.coverImage = `images/${basename(inputData.coverImage)}`;
  }
  // 音频路径
  if (inputData.voicePath && !inputData.voicePath.startsWith('data:')) {
    inputData.voicePath = `audio/${basename(inputData.voicePath)}`;
  }
  if (inputData.bgmPath && !inputData.bgmPath.startsWith('data:')) {
    inputData.bgmPath = `audio/${basename(inputData.bgmPath)}`;
  }

  if (!inputData.domain) inputData.domain = 'education';

  console.log('   图片路径:', inputData.segments[0]?.image);
  console.log('   配音路径:', inputData.voicePath);
  console.log('   BGM路径:', inputData.bgmPath);

  console.log('\n2. 打包 Remotion 组件...');
  const bundled = await bundle({ entryPoint: join(__dirname, 'src', 'index.ts') });
  console.log('   打包完成');

  console.log('\n3. 选择 Composition...');
  const composition = await selectComposition({
    serveUrl: bundled, id: 'VideoComposition', inputProps: { data: inputData },
  });
  console.log('   时长:', composition.durationInFrames, '帧 =', (composition.durationInFrames / 30).toFixed(1), '秒');

  console.log('\n4. 渲染视频...');
  const outputPath = join(__dirname, '..', 'data', 'projects', 'edu_test', 'output', 'final_remotion.mp4');
  await renderMedia({
    composition, serveUrl: bundled, codec: 'h264', outputLocation: outputPath,
    inputProps: { data: inputData },
    onProgress: ({ progress }) => {
      const pct = Math.floor(progress * 100);
      if (pct % 10 === 0) process.stdout.write(` ${pct}%`);
    },
  });
  console.log('\n\n渲染完成!\n输出:', outputPath);
}

main().catch(e => { console.error('渲染失败:', e.message); process.exit(1); });
