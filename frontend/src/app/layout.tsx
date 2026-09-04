import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ApplicationShell } from "@/components/shell/application-shell";
import { loadPresentationContract } from "@/lib/presentation/contract-loader";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "THREADLINE | Analytics Engineering Platform",
  description: "An end-to-end analytics engineering platform that transforms governed source data into traceable analytical and executive reporting.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  await loadPresentationContract();

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <ApplicationShell>{children}</ApplicationShell>
      </body>
    </html>
  );
}
