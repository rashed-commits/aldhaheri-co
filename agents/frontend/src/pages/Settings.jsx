import { useCallback, useEffect, useState } from 'react'
import Header from '../components/Header'
import AppNav from '../components/AppNav'
import { COLORS } from '../config/theme'
import { getUserProfile, updateUserProfile } from '../services/user_profile'

/**
 * Settings page: USER.md editor + auto-accept-memory toggle.
 *
 * USER.md is loaded into a monospace textarea; saving creates a new
 * version. The auto-accept toggle flips a singleton flag — when on,
 * reflection-proposed memory updates apply immediately without surfacing
 * a card. Skill proposals stay gated regardless.
 */
export default function Settings() {
  const [profile, setProfile] = useState(null)
  const [draft, setDraft] = useState('')
  const [autoAccept, setAutoAccept] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [savedAt, setSavedAt] = useState(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const data = await getUserProfile()
      setProfile(data)
      setDraft(data.content_md || '')
      setAutoAccept(!!data.auto_accept_memory)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  const isDirty =
    profile &&
    (draft !== profile.content_md || autoAccept !== !!profile.auto_accept_memory)

  const handleSave = useCallback(async () => {
    if (saving || !isDirty) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateUserProfile({
        content_md: draft,
        auto_accept_memory: autoAccept,
      })
      setProfile(updated)
      setDraft(updated.content_md || '')
      setAutoAccept(!!updated.auto_accept_memory)
      setSavedAt(Date.now())
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }, [draft, autoAccept, isDirty, saving])

  // Quick-toggle: changing the auto-accept switch persists immediately
  // (no need to also edit USER.md to save it).
  const handleToggleAutoAccept = useCallback(async (next) => {
    setAutoAccept(next)
    setError(null)
    try {
      const updated = await updateUserProfile({ auto_accept_memory: next })
      setProfile(updated)
      setSavedAt(Date.now())
    } catch (err) {
      setError(err.message)
      setAutoAccept(!next) // roll back UI
    }
  }, [])

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: COLORS.bgBase,
      color: COLORS.textPrimary,
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Header />
      <AppNav />

      <main style={{
        flex: 1,
        padding: '32px 16px 48px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
        <div style={{ width: '100%', maxWidth: 760 }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', margin: 0 }}>
            Settings
          </h1>
          <p style={{ fontSize: 13, color: COLORS.textMuted, margin: '6px 0 24px' }}>
            Global preferences seen by every agent on every turn, plus
            office-wide automation toggles.
          </p>

          {/* Auto-accept toggle */}
          <div style={{
            padding: 16,
            borderRadius: 12,
            backgroundColor: COLORS.bgCard,
            border: `1px solid ${COLORS.border}`,
            marginBottom: 20,
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <input
                type="checkbox"
                id="auto-accept"
                checked={autoAccept}
                disabled={loading}
                onChange={(e) => handleToggleAutoAccept(e.target.checked)}
                style={{ marginTop: 4, width: 18, height: 18, accentColor: COLORS.accent }}
              />
              <label htmlFor="auto-accept" style={{ flex: 1, cursor: 'pointer' }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  Auto-accept memory proposals
                </div>
                <div style={{ fontSize: 12, color: COLORS.textMuted, marginTop: 4, lineHeight: 1.55 }}>
                  When on, reflection-proposed memory updates apply
                  immediately to the agent's MEMORY.md without surfacing an
                  approval card. Skill proposals always stay gated.
                </div>
              </label>
            </div>
          </div>

          {/* USER.md editor */}
          <div style={{
            padding: 16,
            borderRadius: 12,
            backgroundColor: COLORS.bgCard,
            border: `1px solid ${COLORS.border}`,
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
              USER.md
              {profile && (
                <span style={{ marginLeft: 10, color: COLORS.textDim, letterSpacing: '0.02em', textTransform: 'none', fontWeight: 500 }}>
                  v{profile.version}
                </span>
              )}
            </div>

            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={loading || saving}
              spellCheck={false}
              rows={18}
              style={{
                width: '100%',
                padding: 12,
                borderRadius: 10,
                border: `1px solid ${COLORS.border}`,
                background: COLORS.bgBase,
                color: COLORS.textPrimary,
                fontSize: 13,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                outline: 'none',
                resize: 'vertical',
                minHeight: 280,
                lineHeight: 1.55,
              }}
              placeholder="# USER.md&#10;&#10;Global preferences and facts every agent will see…"
            />

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
              <button
                onClick={handleSave}
                disabled={saving || !isDirty}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: saving || !isDirty ? COLORS.border : COLORS.accent,
                  color: COLORS.textPrimary,
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: saving || !isDirty ? 'default' : 'pointer',
                }}
              >
                {saving ? 'Saving…' : isDirty ? 'Save changes' : 'No changes'}
              </button>
              {savedAt && !isDirty && (
                <span style={{ fontSize: 12, color: COLORS.success }}>Saved</span>
              )}
            </div>
          </div>

          {error && (
            <div style={{
              marginTop: 14,
              padding: '10px 12px',
              borderRadius: 8,
              backgroundColor: COLORS.bgCard,
              border: `1px solid ${COLORS.danger}`,
              color: COLORS.danger,
              fontSize: 13,
            }}>
              {error}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
