import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'UPSC Memory OS — Adaptive Revision System',
  description: 'AI-powered adaptive revision system for UPSC Civil Services preparation. Upload PDFs, ask questions, generate flashcards, and track revision urgency.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen bg-sky-50">
        {children}
      </body>
    </html>
  );
}
