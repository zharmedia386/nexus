// Kept in sync with docs/brand/build_kit.py: the N as a three-hop walk ending on the answer node.
export function LogoMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M16 40V16L48 48V16" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="16" cy="48" r="6" fill="none" stroke="currentColor" strokeWidth="4" />
      <circle cx="16" cy="16" r="4.5" fill="currentColor" />
      <circle cx="48" cy="48" r="4.5" fill="currentColor" />
      <circle cx="48" cy="16" r="7" fill="var(--color-node-person)" />
    </svg>
  );
}
