import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes, InputHTMLAttributes } from 'react';
import { Link, NavLink } from 'react-router-dom';
import type { Verdict } from '../lib/api';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

export function Button({ variant = 'primary', className, busy, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost'; busy?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-[15px] font-semibold transition-colors disabled:opacity-55',
        variant === 'primary' && 'border-transparent bg-brand text-brand-ink hover:opacity-90',
        variant === 'secondary' && 'border-line bg-card text-ink hover:border-muted',
        variant === 'ghost' && 'border-transparent bg-transparent text-ink hover:bg-sunken',
        className,
      )}
    >
      {busy ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cx('rounded-xl border border-line bg-card', className)}>{children}</section>;
}

export function Label({ children }: { children: ReactNode }) {
  return <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">{children}</p>;
}

export function Field({ label, hint, htmlFor, children }: { label: string; hint?: ReactNode; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-semibold">{label}</label>
      {children}
      {hint ? <p className="text-sm text-muted">{hint}</p> : null}
    </div>
  );
}

const inputCls = 'w-full rounded-lg border border-line bg-card px-3 py-2.5 text-[15px] text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20';
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputCls, 'pr-8', props.className)} />;
}

/** A row of mutually exclusive choices. Clicking the selected one clears it ("I'd rather not say"). */
export function Choice<T extends string>({ value, options, onChange, label }: {
  value: T | undefined; options: [T, string][]; onChange: (v: T | undefined) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={value === v}
          onClick={() => onChange(value === v ? undefined : v)}
          className={cx(
            'rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-colors',
            value === v ? 'border-brand bg-brand text-brand-ink' : 'border-line bg-card hover:border-muted',
          )}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export function YesNo({ value, onChange, label }: { value: boolean | undefined; onChange: (v: boolean | undefined) => void; label: string }) {
  return (
    <Choice
      label={label}
      value={value === undefined ? undefined : value ? 'yes' : 'no'}
      options={[['yes', 'Yes'], ['no', 'No']]}
      onChange={(v) => onChange(v === undefined ? undefined : v === 'yes')}
    />
  );
}

const STAMP: Record<Verdict, [string, string]> = {
  eligible: ['text-yes', 'You qualify'],
  maybe: ['text-maybe', 'Check these'],
  not_eligible: ['text-no', 'Not a match'],
};
export function Stamp({ v }: { v: Verdict }) {
  const [c, t] = STAMP[v];
  return <span className={cx('stamp', c)}>{t}</span>;
}

export function Logo() {
  return (
    <Link to="/" className="inline-flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="7" fill="var(--ink)" />
        <path d="M8 11l8-4 8 4-8 4z" fill="var(--gold)" />
        <path d="M11 13v5c0 2 2.5 3.5 5 3.5s5-1.5 5-3.5v-5" fill="none" stroke="var(--paper)" strokeWidth="2" />
        <circle cx="23.5" cy="21.5" r="3.2" fill="var(--yes)" />
      </svg>
      <span className="display text-xl font-semibold">ScholarSathi</span>
    </Link>
  );
}

export function Shell({ children, wide }: { children: ReactNode; wide?: boolean }) {
  const tab = ({ isActive }: { isActive: boolean }) =>
    cx('rounded-lg px-3 py-1.5 text-sm font-semibold', isActive ? 'bg-ink text-paper' : 'text-muted hover:bg-sunken hover:text-ink');
  return (
    <div className="min-h-full">
      <header className="border-b border-line bg-card/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Logo />
          <nav className="flex flex-wrap gap-1">
            <NavLink to="/check" className={tab}>Check eligibility</NavLink>
            <NavLink to="/ask" className={tab}>Ask</NavLink>
            <NavLink to="/schemes" className={tab}>All schemes</NavLink>
            <NavLink to="/sources" className={tab}>Sources</NavLink>
          </nav>
        </div>
      </header>
      <main className={cx('mx-auto px-4 py-8 sm:px-6', wide ? 'max-w-6xl' : 'max-w-4xl')}>{children}</main>
      <footer className="border-t border-line">
        <p className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted sm:px-6">
          ScholarSathi is an independent student project, not a government website. Rules come from the official guidelines
          linked on every result; always confirm on the official portal before applying.
        </p>
      </footer>
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-lg border border-no/40 bg-no/10 px-3.5 py-2.5 text-sm text-no">{children}</div>;
}
