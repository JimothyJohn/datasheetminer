/**
 * NetworkStatus: Online/Offline indicator component
 *
 * Displays a notification banner when the user's internet connection is lost.
 * Automatically detects connection changes and provides visual feedback.
 *
 * Features:
 * - Automatic online/offline detection
 * - Slide-in animation for smooth UX
 * - Non-intrusive banner at top of screen
 * - Auto-dismisses when connection restored
 * - Works on mobile and desktop
 *
 * Browser Support:
 * - navigator.onLine API (supported in all modern browsers)
 * - Online/offline events (Safari, Chrome, Firefox, Edge)
 *
 * Mobile Considerations:
 * - Helps users understand why requests are failing
 * - Prevents confusion on spotty mobile connections
 * - Important for offline PWA functionality
 *
 * @module NetworkStatus
 */

import { useState, useEffect } from 'react';

export default function NetworkStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [showOfflineMessage, setShowOfflineMessage] = useState(!navigator.onLine);

  useEffect(() => {
    console.log('[NetworkStatus] Initial connection status:', isOnline ? 'ONLINE' : 'OFFLINE');

    const handleOnline = () => {
      console.log('[NetworkStatus] Connection restored: ONLINE');
      setIsOnline(true);
      setShowOfflineMessage(false);
    };

    const handleOffline = () => {
      console.log('[NetworkStatus] Connection lost: OFFLINE');
      setIsOnline(false);
      setShowOfflineMessage(true);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [isOnline]);

  if (!showOfflineMessage) return null;

  const styles = {
    banner: {
      position: 'fixed' as const,
      top: 0,
      left: 0,
      right: 0,
      backgroundColor: '#ff6b6b',
      color: 'white',
      padding: '12px 20px',
      textAlign: 'center' as const,
      fontSize: '14px',
      fontWeight: 500,
      zIndex: 9999,
      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      animation: 'slideDown 0.3s ease-out',
    },
    content: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
    },
  };

  return (
    <>
      <style>
        {`
          @keyframes slideDown {
            from {
              transform: translateY(-100%);
              opacity: 0;
            }
            to {
              transform: translateY(0);
              opacity: 1;
            }
          }
        `}
      </style>
      <div style={styles.banner} role="alert" aria-live="assertive">
        <div style={styles.content}>
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="1" y1="1" x2="23" y2="23" />
            <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
            <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
            <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
            <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
            <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
            <line x1="12" y1="20" x2="12.01" y2="20" />
          </svg>
          <span>
            <strong>No internet connection.</strong> Some features may not work properly.
          </span>
        </div>
      </div>
    </>
  );
}
