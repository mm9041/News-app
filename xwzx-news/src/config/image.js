/**
 * 图片加载失败的兜底。
 *
 * 新闻配图来自第三方图床（picsum.photos）。2026-09-26 就出现过一批图片 ID
 * 在该图床上不存在、接口直接返回 404 的情况，页面上于是显示成破图。
 * 外链始终有失效的可能（图床改规则、图片被删、网络不通），所以统一兜一层。
 *
 * 占位图用内联的 data URI 而不是再引一个外链 —— 兜底本身不能再失败。
 */
const PLACEHOLDER_SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">',
  '<rect width="200" height="200" fill="#f2f3f5"/>',
  '<circle cx="70" cy="74" r="14" fill="#d8dbe0"/>',
  '<path d="M26 154 L78 104 L112 138 L142 110 L174 154 Z" fill="#d8dbe0"/>',
  '</svg>',
].join('')

export const PLACEHOLDER_IMAGE =
  'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(PLACEHOLDER_SVG)

/**
 * 用法：`<img :src="..." @error="onImageError">`
 *
 * 用 dataset 打标记，避免占位图本身再触发 error 时无限循环。
 */
export function onImageError(event) {
  const img = event?.target
  if (!img || img.dataset.fallbackApplied) return
  img.dataset.fallbackApplied = '1'
  img.src = PLACEHOLDER_IMAGE
}
