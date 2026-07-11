/**
 * 资源路径解析 - 基于 OpenMontage 的 resolveAsset
 * 处理所有路径格式：Windows绝对路径、file://、http、data:、relative
 */
import { staticFile } from 'remotion';

export function resolveAsset(src: string): string {
  if (!src) return '';

  // data URL / http URL - 直接返回
  if (src.startsWith('data:') || src.startsWith('http://') || src.startsWith('https://')) return src;

  // file:// URI - 清理后返回
  if (src.startsWith('file://')) return src;

  // Windows绝对路径 (F:\... or F:/...) -> file:/// URI
  if (/^[A-Za-z]:[\\/]/.test(src)) {
    return `file:///${src.replace(/\\/g, '/')}`;
  }

  // Unix绝对路径 (/...) -> file:/// URI
  if (src.startsWith('/')) {
    return `file://${src}`;
  }

  // 相对路径 -> staticFile()
  try {
    return staticFile(src);
  } catch {
    return src;
  }
}
