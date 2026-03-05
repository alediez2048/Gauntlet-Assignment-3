import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "DOGE Lense — Legacy Code Intelligence",
  description:
    "RAG-powered legacy code intelligence. Ask questions about COBOL and Fortran codebases in natural language.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 antialiased`}>
        {children}
      </body>
    </html>
  );
}
