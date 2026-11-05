import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'AI MetroFlow - Metro Crowd Management & Scheduling',
  description: 'AI-powered platform for metro crowd monitoring, prediction, and schedule optimization',
  keywords: ['metro', 'transit', 'crowd management', 'AI', 'scheduling', 'smart city'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} antialiased`}>
      <body className="bg-secondary-50 text-secondary-900">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}