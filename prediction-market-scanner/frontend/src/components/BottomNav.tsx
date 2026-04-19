"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/", label: "Markets", icon: "📊" },
  { href: "/whales", label: "Whales", icon: "🐋" },
  { href: "/overlap", label: "Overlap", icon: "🎯" },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-700 safe-bottom z-50">
      <div className="flex max-w-2xl mx-auto">
        {tabs.map((tab) => {
          const active =
            tab.href === "/"
              ? pathname === "/" || pathname.startsWith("/market/")
              : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex-1 flex flex-col items-center py-2 text-xs transition-colors ${
                active ? "text-green-400" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              <span className="text-lg leading-none mb-0.5">{tab.icon}</span>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
