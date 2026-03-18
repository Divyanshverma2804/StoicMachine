import React, { useState, useRef } from 'react'
import Header from './components/layout/Header'
import QueueTab from './components/jobs/QueueTab'
import CalendarTab from './components/calendar/CalendarView'
import DiaryTab from './components/diary/DiaryView'
import AnalyticsTab from './components/analytics/AnalyticsView'
import { Toaster } from 'react-hot-toast'

export default function App() {
  const [tab, setTab] = useState('queue')
  // Ref to pass content from diary → queue submit
  const queueContentRef = useRef(null)

  const handleOpenInQueue = (content) => {
    // Store in sessionStorage so SubmitForm picks it up
    sessionStorage.setItem('rf_content', content)
    // Force SubmitForm to re-read by switching tabs
    setTab('queue')
    // Brief delay to let SubmitForm mount and pick up sessionStorage
    setTimeout(() => window.dispatchEvent(new Event('rf_load_content')), 100)
  }

  return (
    <>
      <Toaster
        position='bottom-right'
        toastOptions={{
          style: {
            background: 'var(--bg-2)',
            color: 'var(--text-0)',
            border: '1px solid var(--line-2)',
            borderRadius: 3,
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            padding: '8px 14px',
          },
          success: {
            iconTheme: { primary: 'var(--accent)', secondary: 'var(--bg-0)' },
          },
        }}
      />

      <Header activeTab={tab} onTabChange={setTab} />

      <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: tab === 'queue'     ? 'flex' : 'none', flex: 1, overflow: 'hidden' }}>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <QueueTab />
          </div>
        </div>
        <div style={{ display: tab === 'calendar'  ? 'flex' : 'none', flex: 1, overflow: 'hidden' }}>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <CalendarTab />
          </div>
        </div>
        <div style={{ display: tab === 'diary'     ? 'flex' : 'none', flex: 1, overflow: 'hidden' }}>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <DiaryTab onOpenInQueue={handleOpenInQueue} />
          </div>
        </div>
        <div style={{ display: tab === 'analytics' ? 'flex' : 'none', flex: 1, overflow: 'hidden' }}>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <AnalyticsTab />
          </div>
        </div>
      </main>
    </>
  )
}
