import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { LogOut, Menu, X } from "lucide-react";
import { SchoolName } from "../components/SchoolMark";
import { useAuth } from "../context/AuthContext";
import { cx } from "../components/ui";

/**
 * Shared shell for both portals: a quiet white sidebar with brown accents on desktop,
 * a slide-in drawer on small screens.
 */
export default function PortalLayout({ portalLabel, nav, headerExtra, sidebarExtra, context, outletContext, children }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const navList = (
    <nav className="flex flex-col gap-1" aria-label={`${portalLabel} sections`}>
      {nav.map((item) => (
        <NavLink key={item.to} to={item.to} onClick={() => setOpen(false)}
          className={({ isActive }) => cx(
            "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition",
            isActive ? "bg-brand-700 text-white shadow-sm" : "text-ink-soft hover:bg-brand-50 hover:text-brand-800",
          )}>
          {({ isActive }) => (
            <>
              <item.icon className={cx("size-[18px]", isActive ? "text-brand-100" : "text-brand-500 group-hover:text-brand-700")} />
              <span className="flex-1">{item.label}</span>
              {item.badge ? (
                <span className={cx("rounded-full px-2 text-xs", isActive ? "bg-white/20 text-white" : "bg-brand-100 text-brand-800")}>{item.badge}</span>
              ) : null}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-5">
      <Link to="/" className="block"><SchoolName sub={portalLabel} /></Link>
      {sidebarExtra}
      {navList}
      <div className="mt-auto rounded-xl border border-line bg-brand-50/60 p-3">
        <p className="truncate text-sm font-semibold text-ink">{user?.name}</p>
        <p className="text-xs text-muted">{user?.role === "teacher" ? user?.employee_code : "Parent / Guardian"}</p>
        <button onClick={logout} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-brand-300 bg-white py-2 text-sm font-medium text-brand-800 hover:bg-brand-50">
          <LogOut className="size-4" /> Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-white">
      <aside className="fixed inset-y-0 left-0 hidden w-[272px] border-r border-line bg-white lg:block">{sidebar}</aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-brand-950/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-[84%] max-w-[300px] overflow-y-auto bg-white shadow-xl">
            <button className="absolute right-3 top-3 rounded-lg p-1.5 text-muted hover:bg-brand-50" onClick={() => setOpen(false)} aria-label="Close menu"><X className="size-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="lg:pl-[272px]">
        <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
            <button className="rounded-lg p-2 text-brand-800 hover:bg-brand-50 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="size-5" /></button>
            <div className="min-w-0 flex-1">{context}</div>
            {headerExtra}
          </div>
        </header>
        <main className="mx-auto max-w-[1240px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children ?? <Outlet context={outletContext} />}
        </main>
      </div>
    </div>
  );
}
