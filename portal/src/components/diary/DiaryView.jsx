import React, { useState, useEffect, useRef } from 'react'
import { useDiary, useCreateDiary, useUpdateDiary, useDeleteDiary } from '../../hooks/useDiary'
import Btn from '../ui/Btn'

const SOURCE_COLORS = {
  posted: '#00e5a0',
  queued: '#7b68ee',
  draft:  '#f5a623',
}

export default function DiaryTab({ onOpenInQueue }) {
  const { data: entries = [], isLoading } = useDiary()
  const createDiary = useCreateDiary()
  const updateDiary = useUpdateDiary()
  const deleteDiary = useDeleteDiary()

  const [activeId, setActiveId]   = useState(null)
  const [title, setTitle]         = useState('')
  const [content, setContent]     = useState('')
  const [search, setSearch]       = useState('')
  const [dirty, setDirty]         = useState(false)
  const titleRef = useRef(null)

  const activeEntry = entries.find(e => e.id === activeId)

  const filtered = entries.filter(e => {
    const q = search.toLowerCase()
    return !q || e.title.toLowerCase().includes(q) || (e.content || '').toLowerCase().includes(q)
  })

  const open = (entry) => {
    setActiveId(entry.id)
    setTitle(entry.title)
    setContent(entry.content || '')
    setDirty(false)
  }

  const newDraft = () => {
    setActiveId(null)
    setTitle('')
    setContent('')
    setDirty(false)
    setTimeout(() => titleRef.current?.focus(), 50)
  }

  const save = async () => {
    const t = title.trim() || 'Untitled'
    if (activeId) {
      await updateDiary.mutateAsync({ id: activeId, fields: { title: t, content } })
    } else {
      const data = await createDiary.mutateAsync({ title: t, content, tag: '' })
      setActiveId(data.id)
    }
    setDirty(false)
  }

  const handleDelete = async () => {
    if (!activeId || !confirm('delete this entry?')) return
    await deleteDiary.mutateAsync(activeId)
    setActiveId(null); setTitle(''); setContent('')
  }

  const titleBlur = async () => {
    if (!dirty || !activeId) return
    const t = title.trim()
    if (!t || t === activeEntry?.title) return
    await updateDiary.mutateAsync({ id: activeId, fields: { title: t } })
  }

  const isSaving = createDiary.isPending || updateDiary.isPending

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '260px 1fr',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* Sidebar */}
      <div style={{
        borderRight: '1px solid var(--line-0)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Search + new */}
        <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--line-0)', flexShrink: 0 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder='search scripts…'
            style={{ width: '100%', padding: '6px 10px', borderRadius: 3, fontSize: 12, marginBottom: 8 }}
          />
          <Btn size='sm' variant='primary' onClick={newDraft} style={{ width: '100%', justifyContent: 'center' }}>
            + new draft
          </Btn>
        </div>

        {/* List */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {isLoading ? (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--text-3)' }}>loading…</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 20, fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>
              no entries yet
            </div>
          ) : filtered.map(entry => (
            <div
              key={entry.id}
              onClick={() => open(entry)}
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--line-0)',
                cursor: 'pointer',
                background: activeId === entry.id ? 'rgba(0,229,160,0.04)' : 'transparent',
                borderLeft: activeId === entry.id ? '2px solid var(--accent)' : '2px solid transparent',
                transition: 'background 0.1s',
              }}
            >
              <div style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-0)',
                marginBottom: 4,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {entry.title}
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  color: SOURCE_COLORS[entry.source] || '#606060',
                  textTransform: 'uppercase',
                }}>
                  {entry.source || 'draft'}
                </span>
                {entry.updated_at && (
                  <span style={{ fontSize: 10, color: 'var(--text-3)' }}>
                    {entry.updated_at.slice(0, 10)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Editor */}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Title bar */}
        <div style={{
          borderBottom: '1px solid var(--line-0)',
          padding: '0 16px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          height: 44,
        }}>
          <input
            ref={titleRef}
            value={title}
            onChange={e => { setTitle(e.target.value); setDirty(true) }}
            onBlur={titleBlur}
            placeholder='entry title…'
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              fontSize: 13,
              fontWeight: 700,
              color: 'var(--text-0)',
              padding: 0,
              outline: 'none',
              letterSpacing: '0.02em',
            }}
          />
        </div>

        {/* Textarea */}
        <textarea
          value={content}
          onChange={e => { setContent(e.target.value); setDirty(true) }}
          placeholder={`# ReelName: silence_wins\n\n## Hook:\nMost people are loud...\n\n## Conflict:\nThey think volume equals strength.\n\n## Shift:\nSilence is power.\n\n## Punch:\nThe quietest person in the room\nis often the most dangerous.\n\n## Engage:\nType IRON if this hit.`}
          style={{
            flex: 1,
            resize: 'none',
            padding: '16px 20px',
            fontSize: 13,
            lineHeight: 1.75,
            color: 'var(--text-1)',
            background: 'var(--bg-0)',
            border: 'none',
            borderBottom: '1px solid var(--line-0)',
            outline: 'none',
            fontFamily: 'var(--font-mono)',
            tabSize: 2,
          }}
        />

        {/* Action bar */}
        <div style={{
          padding: '10px 16px',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          background: 'var(--bg-1)',
          flexShrink: 0,
          borderTop: '1px solid var(--line-0)',
        }}>
          <Btn variant='primary' size='sm' onClick={save} disabled={isSaving}>
            {isSaving ? 'saving…' : dirty ? 'save *' : 'saved'}
          </Btn>
          <Btn size='sm' onClick={() => { save().then(() => onOpenInQueue(content)) }}>
            ↑ open in queue
          </Btn>
          {activeId && (
            <Btn size='sm' variant='danger' onClick={handleDelete}>
              delete
            </Btn>
          )}
          {activeId && (
            <span style={{ fontSize: 10, color: 'var(--text-3)', marginLeft: 4 }}>
              #{activeId}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
