import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Skill Forge Dashboard",
  description: "Live view of Skill Forge learning new skills.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-bg text-text min-h-screen">
        <div className="min-h-screen flex flex-col">{children}</div>
      </body>
    </html>
  );
}

