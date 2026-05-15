/**
 * Design system colors from the root CLAUDE.md.
 * Use inline styles in components (matches the hub pattern).
 */
export const COLORS = {
  bgBase: '#0F0F1A',
  bgCard: '#1A1A2E',
  bgCardSubtle: '#15152A',
  border: '#2D2D4E',
  borderSoft: '#222238',
  accent: '#7C3AED',
  accentLight: '#A78BFA',
  textPrimary: '#F1F5F9',
  textMuted: '#94A3B8',
  textDim: '#5A5856',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
}

/** Status -> color mapping for sprite/badge tinting. */
export const STATUS_COLORS = {
  idle: COLORS.textMuted,
  thinking: COLORS.warning,
  working: COLORS.accent,
  done: COLORS.success,
  error: COLORS.danger,
}
