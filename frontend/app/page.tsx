'use client';

import { useState } from 'react';
import type { CSSProperties } from 'react';

export default function SimpleUploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState('');
  const [paperId, setPaperId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleUpload() {
    if (!file) {
      setStatus('⚠️ Please select a file first');
      return;
    }

    setLoading(true);
    setStatus('Uploading...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      setPaperId(data.paper_id);
      setStatus('✅ Upload successful!');
    } catch (e) {
      setStatus('❌ Connection error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>AI Document Analyzer</h1>
        <p style={styles.subtitle}>Upload your paper for instant insights</p>

        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          style={styles.input}
        />

        <button
          onClick={handleUpload}
          disabled={loading}
          style={{
            ...styles.button,
            opacity: loading ? 0.6 : 1,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Processing...' : 'Upload & Analyze'}
        </button>

        {status && <p style={styles.status}>{status}</p>}

        {paperId && (
          <div style={styles.resultBox}>
            <p>📄 Paper ID: <b>{paperId}</b></p>
            <a href={`/analysis/${paperId}`} style={styles.link}>
              View Analysis →
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    height: '100vh',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    background: 'radial-gradient(circle at top, #1e293b, #0f172a)',
    fontFamily: 'sans-serif',
  },

  card: {
    width: '380px',
    padding: '32px',
    borderRadius: '16px',
    background: 'rgba(255, 255, 255, 0.06)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
    textAlign: 'center',
    color: '#e5e7eb',
  },

  title: {
    fontSize: '22px',
    fontWeight: 700,
    marginBottom: '6px',
    color: '#ffffff',
  },

  subtitle: {
    fontSize: '13px',
    marginBottom: '20px',
    color: '#94a3b8',
  },

  input: {
    width: '100%',
    marginBottom: '14px',
    padding: '10px',
    borderRadius: '8px',
    background: '#0f172a',
    border: '1px solid #334155',
    color: '#e5e7eb',
  },

  button: {
    width: '100%',
    padding: '10px',
    borderRadius: '10px',
    border: 'none',
    background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
    color: '#fff',
    fontSize: '14px',
    fontWeight: 600,
    transition: '0.2s ease',
  },

  status: {
    marginTop: '12px',
    fontSize: '13px',
    color: '#cbd5e1',
  },

  resultBox: {
    marginTop: '18px',
    padding: '14px',
    borderRadius: '10px',
    background: 'rgba(59, 130, 246, 0.1)',
    border: '1px solid rgba(59, 130, 246, 0.3)',
  },

  link: {
    color: '#60a5fa',
    textDecoration: 'none',
    fontWeight: 500,
  },
};