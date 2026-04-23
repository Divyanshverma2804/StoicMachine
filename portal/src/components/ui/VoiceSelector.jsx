import React, { useState, useEffect } from 'react'

export default function VoiceSelector({ value, onChange }) {
  const [voices, setVoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [previewingVoice, setPreviewingVoice] = useState(null)

  useEffect(() => {
    const fetchVoices = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch('/voices')
        if (!response.ok) throw new Error('Failed to load voices')
        const data = await response.json()
        setVoices(data || [])
      } catch (err) {
        setError(err.message)
        console.error('Failed to fetch voices:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchVoices()
  }, [])

  const selectedVoice = voices.find(v => v.filename === value)

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      {/* Header */}
      <div style={{
        fontSize: 10,
        color: 'var(--text-2)',
        letterSpacing: '0.06em',
        marginBottom: 3,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <span>SPEAKER VOICE</span>
        {value && <span style={{ fontSize: 9, color: 'var(--accent)' }}>✓ selected</span>}
      </div>

      {/* Loading state */}
      {loading && (
        <div style={{
          padding: '12px',
          backgroundColor: 'rgba(255, 220, 0, 0.08)',
          borderRadius: 4,
          fontSize: 11,
          color: 'var(--text-3)',
        }}>
          Loading voices...
        </div>
      )}

      {/* Error state */}
      {error && (
        <div style={{
          padding: '12px',
          backgroundColor: 'rgba(255, 100, 100, 0.08)',
          borderRadius: 4,
          fontSize: 11,
          color: 'var(--accent-red)',
        }}>
          Could not load voices: {error}
        </div>
      )}

      {/* Voice selector grid */}
      {!loading && voices.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
          gap: 8,
        }}>
          {/* Default voice option */}
          <button
            type="button"
            onClick={() => {
              onChange('')
              setPreviewingVoice(null)
            }}
            onMouseEnter={() => setPreviewingVoice('default')}
            onMouseLeave={() => setPreviewingVoice(null)}
            style={{
              padding: '10px 12px',
              backgroundColor: !value ? 'rgba(0, 229, 160, 0.1)' : 'var(--bg-1)',
              border: `2px solid ${!value ? 'var(--accent)' : 'var(--line-1)'}`,
              borderRadius: 6,
              color: 'var(--text-1)',
              fontSize: 11,
              fontWeight: !value ? '600' : '400',
              cursor: 'pointer',
              transition: 'all 0.2s',
              textAlign: 'center',
              lineHeight: 1.4,
            }}
          >
            <div style={{ fontWeight: '600', marginBottom: 2 }}>✨</div>
            <div>AI Default</div>
            <div style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 2 }}>Standard voice</div>
          </button>

          {/* Voice options */}
          {voices.map(voice => (
            <button
              key={voice.filename}
              type="button"
              onClick={() => {
                onChange(voice.filename)
                setPreviewingVoice(voice.filename)
              }}
              onMouseEnter={() => setPreviewingVoice(voice.filename)}
              onMouseLeave={() => setPreviewingVoice(previewingVoice === voice.filename ? null : previewingVoice)}
              style={{
                padding: '10px 12px',
                backgroundColor: value === voice.filename ? 'rgba(0, 229, 160, 0.1)' : 'var(--bg-1)',
                border: `2px solid ${value === voice.filename ? 'var(--accent)' : 'var(--line-1)'}`,
                borderRadius: 6,
                color: 'var(--text-1)',
                fontSize: 11,
                fontWeight: value === voice.filename ? '600' : '400',
                cursor: 'pointer',
                transition: 'all 0.2s',
                textAlign: 'center',
                lineHeight: 1.4,
                position: 'relative',
              }}
            >
              <div style={{ fontWeight: '600', marginBottom: 2 }}>🎙️</div>
              <div style={{ 
                overflow: 'hidden', 
                textOverflow: 'ellipsis', 
                whiteSpace: 'nowrap',
                maxWidth: '100%',
              }}>
                {voice.name}
              </div>
              {previewingVoice === voice.filename && (
                <div style={{
                  position: 'absolute',
                  bottom: -2,
                  right: -2,
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  backgroundColor: 'var(--accent)',
                  fontSize: 8,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  ●
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && voices.length === 0 && !error && (
        <div style={{
          padding: '12px',
          backgroundColor: 'var(--bg-1)',
          borderRadius: 4,
          fontSize: 11,
          color: 'var(--text-3)',
          border: '1px solid var(--line-1)',
          textAlign: 'center',
        }}>
          No voices available. Add voice files to the voices/ directory.
        </div>
      )}

      {/* Info box */}
      {selectedVoice && (
        <div style={{
          padding: '10px 12px',
          backgroundColor: 'rgba(0, 229, 160, 0.05)',
          borderRadius: 4,
          fontSize: 10,
          color: 'var(--text-2)',
          border: '1px solid rgba(0, 229, 160, 0.2)',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-start',
        }}>
          <div style={{ flexShrink: 0, marginTop: 2 }}>ℹ️</div>
          <div>
            <strong>{selectedVoice.name}</strong> voice will be used for all reels in this batch
          </div>
        </div>
      )}
    </div>
  )
}
