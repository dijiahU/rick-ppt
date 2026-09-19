// Keep aligned with the execution bridge's outline.py.
export const MAX_SLIDES = 50;
export const MAX_PROGRESS_BYTES = 2 * 1024 * 1024;
/** @param {string} value */
export function validSlideKey(value) {
  return /^[1-9]\d*$/.test(value) && Number(value) <= MAX_SLIDES;
}
