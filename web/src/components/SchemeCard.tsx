import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { MatchResult, Scheme } from '../lib/api';
import { SourceLine } from './Citations';
import { Card, Stamp, cx } from './ui';

const ICON = {
  pass: ['✓', 'text-yes', 'Meets this'],
  fail: ['✗', 'text-no', 'Does not meet this'],
  unknown: ['?', 'text-maybe', 'Not answered yet'],
  info: ['•', 'text-muted', 'Rule'],
} as const;

export function RuleRow({ state, label, source }: { state: keyof typeof ICON; label: string; source: Scheme['rules'][number]['source'] }) {
  const [sym, color, sr] = ICON[state];
  return (
    <li className="flex gap-2.5">
      <span className={cx('w-4 shrink-0 text-center font-bold', color)} aria-label={sr}>{sym}</span>
      <span className="min-w-0">
        <span className={state === 'fail' ? 'text-ink' : undefined}>{label}</span>{' '}
        <SourceLine s={source} />
      </span>
    </li>
  );
}

export function SchemeCard({ m, scheme, open: initiallyOpen = false }: { m?: MatchResult; scheme?: Scheme; open?: boolean }) {
  const s = (m?.scheme ?? scheme)!;
  const [open, setOpen] = useState(initiallyOpen);
  const state = (id: string): keyof typeof ICON =>
    !m ? 'info' : m.passed.includes(id) ? 'pass' : m.failed.includes(id) ? 'fail' : 'unknown';

  return (
    <Card className="rise p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-muted">{s.ministry}{s.kind === 'state' ? ' · State scheme' : ''}</p>
          <h3 className="display mt-1 text-xl font-semibold">
            <Link to={`/schemes/${s.id}`} className="hover:underline">{s.short}</Link>
          </h3>
          <p className="mt-1 text-muted">{s.forWhom}</p>
        </div>
        {m ? <Stamp v={m.verdict} /> : null}
      </div>

      <p className="mt-3"><span className="mark font-semibold">{s.benefit}</span></p>

      {m && m.verdict === 'not_eligible' && !open ? (
        <p className="mt-3 text-sm">
          <span className="font-semibold text-no">Why not: </span>
          {s.rules.filter((r) => m.failed.includes(r.id)).map((r) => r.label).join('; ')}
        </p>
      ) : null}
      {m && m.verdict === 'maybe' && !open ? (
        <p className="mt-3 text-sm">
          <span className="font-semibold text-maybe">To confirm: </span>
          {s.rules.filter((r) => m.unknown.includes(r.id)).map((r) => r.label).join('; ')}
        </p>
      ) : null}

      {open ? (
        <div className="mt-4 grid gap-4 border-t border-line pt-4">
          <div>
            <p className="mb-2 text-sm font-bold">Eligibility rules</p>
            <ul className="grid gap-2 text-[15px]">
              {s.rules.map((r) => <RuleRow key={r.id} state={state(r.id)} label={r.label} source={r.source} />)}
            </ul>
          </div>
          {s.checks.length ? (
            <div>
              <p className="mb-2 text-sm font-bold">Also required (check yourself)</p>
              <ul className="grid gap-2 text-[15px]">
                {s.checks.map((c, i) => <RuleRow key={i} state="info" label={c.text} source={c.source} />)}
              </ul>
            </div>
          ) : null}
          {s.notes.length ? (
            <div className="rounded-lg bg-gold-soft px-3.5 py-2.5 text-sm">
              {s.notes.map((n, i) => <p key={i}>{n}</p>)}
            </div>
          ) : null}
          <p className="text-sm text-muted"><span className="font-semibold text-ink">When:</span> {s.window}</p>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setOpen((o) => !o)} className="rounded-lg border border-line px-3 py-1.5 text-sm font-semibold hover:border-muted" aria-expanded={open}>
          {open ? 'Hide rules' : 'See rules and sources'}
        </button>
        <Link to={`/ask?scheme=${s.id}`} className="rounded-lg border border-line px-3 py-1.5 text-sm font-semibold hover:border-muted">
          Ask about this
        </Link>
        {s.applyUrl ? (
          <a href={s.applyUrl} target="_blank" rel="noreferrer" className="rounded-lg bg-brand px-3 py-1.5 text-sm font-semibold text-brand-ink hover:opacity-90">
            Apply on official portal ↗
          </a>
        ) : null}
      </div>
    </Card>
  );
}
