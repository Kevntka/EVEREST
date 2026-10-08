/**
 * Placeholder cover for events without a cover photo: the title's first letter on a
 * random color. Each title gets its color the first time it is shown and keeps it until
 * the app reloads, so it doesn't flicker on every redraw or the 10-second auto-refresh,
 * and an event looks the same on the dashboard and on Event Details.
 */
const COVER_COLORS = [
  '#e74c3c', '#e67e22', '#f39c12', '#27ae60', '#16a085', '#2980b9',
  '#3b5998', '#8e44ad', '#c0392b', '#d35400', '#2c3e50', '#7f8c8d',
  '#00897b', '#5e35b1', '#d81b60', '#6d4c41',
];

const assignedColors = new Map<string, string>();
let lastColor = '';

/** First letter or digit of the title, uppercase ("?" when there is none). */
export function coverInitial(title: string | null | undefined): string {
  const match = (title || '').match(/[\p{L}\p{N}]/u);
  return match ? match[0].toUpperCase() : '?';
}

/** Random background color for the title's placeholder cover (fixed once picked). */
export function coverColor(title: string | null | undefined): string {
  const key = (title || '').trim().toLowerCase();
  let color = assignedColors.get(key);
  if (!color) {
    // Skip the previous pick so cards next to each other don't share a color
    const choices = COVER_COLORS.filter(c => c !== lastColor);
    color = choices[Math.floor(Math.random() * choices.length)];
    assignedColors.set(key, color);
    lastColor = color;
  }
  return color;
}
