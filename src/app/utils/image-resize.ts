/**
 * Shrinks large photos (e.g. 4K) in the browser before upload so they fit the
 * backend's 5 MB cover limit and don't waste database space. Covers are shown at
 * most ~1000px wide, so 1920px on the long side is plenty.
 */
export const MAX_COVER_SIDE = 1920;

/**
 * Returns the photo scaled down to MAX_COVER_SIDE (as WebP, or JPEG where the browser
 * can't encode WebP). Small photos and GIFs (which may be animated) are returned as is.
 */
export async function shrinkImage(file: File, maxSide = MAX_COVER_SIDE): Promise<File> {
  if (file.type === 'image/gif') return file;

  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  // Already small: keep the original unless it is heavy (over 2 MB) and worth re-encoding
  if (scale === 1 && file.size <= 2 * 1024 * 1024) {
    bitmap.close();
    return file;
  }

  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  let blob = await toBlob(canvas, 'image/webp', 0.85);
  if (!blob || blob.type !== 'image/webp') blob = await toBlob(canvas, 'image/jpeg', 0.85);
  if (!blob || blob.size >= file.size) return file;  // re-encoding didn't help

  const ext = blob.type === 'image/webp' ? 'webp' : 'jpg';
  const name = file.name.replace(/\.[^.]+$/, '') + '.' + ext;
  return new File([blob], name, { type: blob.type });
}

function toBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob | null> {
  return new Promise(resolve => canvas.toBlob(resolve, type, quality));
}
