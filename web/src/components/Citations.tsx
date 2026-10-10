import { Fragment, useState, type ReactNode } from 'react';
import type { Citation, Source } from '../lib/api';
import { cx } from './ui';

/** Link to a PDF page. Most browsers' PDF viewers honour #page=N. */
export const pageUrl = (url: string, page?: number | null) => (page && /\.pdf($|\?)/i.test(url) ? `${url}#page=${page}` : url);

/** A rule's source: document, clause and (when we have it) the exact words. */
export function SourceLine({ s }: { s: Source }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="text-sm text-muted">
      <button type="button" onClick={() => setOpen((o) => !o)} className="underline decoration-dotted underline-offset-2 hover:text-ink"
        aria-expanded={open}>
        {s.location ? `${s.location}` : 'Source'}
      </button>
      {open ? (
        <span className="rise mt-2 block rounded-lg border border-line bg-sunken p-3 text-ink">
          {s.quote ? <q className="block italic">{s.quote}</q> : null}
          <a href={s.url} target="_blank" rel="noreferrer" className="mt-1 block font-semibold text-brand hover:underline">
            {s.title} ↗
          </a>
          <span className="block text-xs text-muted">{s.version}</span>
        </span>
      ) : null}
    </span>
  );
}

/** Inline [S1] markers in an answer, turned into numbered chips. */
function Chip({ n, active, onClick }: { n: number; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label={`Source ${n}`}
      className={cx('mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded px-1 align-[2px] text-[11px] font-bold',
        active ? 'bg-brand text-brand-ink' : 'bg-sunken text-brand hover:bg-brand hover:text-brand-ink')}>
      {n}
    </button>
  );
}

/** Minimal markdown: paragraphs, "- " lists, **bold**, and [S#] citation chips. */
export function AnswerText({ text, citations, active, setActive }: {
  text: string; citations: Citation[]; active: number | null; setActive: (n: number | null) => void;
}) {
  const known = new Set(citations.map((c) => c.n));
  const inline = (s: string, key: string): ReactNode[] =>
    s.split(/(\[S\d+\]|\*\*[^*]+\*\*)/g).map((part, i) => {
      const m = part.match(/^\[S(\d+)\]$/);
      if (m) {
        const n = Number(m[1]);
        return known.has(n) ? <Chip key={`${key}-${i}`} n={n} active={active === n} onClick={() => setActive(active === n ? null : n)} /> : null;
      }
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>;
      return <Fragment key={`${key}-${i}`}>{part}</Fragment>;
    });

  const blocks = text.split(/\n{2,}/);
  return (
    <div className="grid gap-3 leading-relaxed">
      {blocks.map((b, bi) => {
        const lines = b.split('\n').filter(Boolean);
        if (lines.length && lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
          return (
            <ul key={bi} className="grid list-disc gap-1.5 pl-5">
              {lines.map((l, li) => <li key={li}>{inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ''), `${bi}-${li}`)}</li>)}
            </ul>
          );
        }
        return <p key={bi}>{lines.map((l, li) => <Fragment key={li}>{li ? <br /> : null}{inline(l, `${bi}-${li}`)}</Fragment>)}</p>;
      })}
    </div>
  );
}

export function CitationList({ citations, active, setActive }: { citations: Citation[]; active: number | null; setActive: (n: number | null) => void }) {
  if (!citations.length) return null;
  return (
    <ol className="grid gap-2">
      {citations.map((c) => (
        <li key={c.n}>
          <button type="button" onClick={() => setActive(active === c.n ? null : c.n)}
            className={cx('flex w-full items-start gap-3 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
              active === c.n ? 'border-brand bg-sunken' : 'border-line hover:border-muted')}
            aria-expanded={active === c.n}>
            <span className="mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-brand px-1 text-[11px] font-bold text-brand-ink">{c.n}</span>
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">{c.title}</span>
              <span className="block text-muted">{[c.section, c.pageLabel].filter(Boolean).join(' · ')}</span>
            </span>
          </button>
          {active === c.n ? (
            <div className="rise mt-1 ml-8 grid gap-2 rounded-lg bg-sunken p-3 text-sm">
              {c.quote ? (
                <p><span className="font-semibold">Quoted: </span><q className="italic">{c.quote}</q></p>
              ) : null}
              <p className="text-muted">{c.excerpt}{c.excerpt.length >= 600 ? '…' : ''}</p>
              <a href={pageUrl(c.url, c.page)} target="_blank" rel="noreferrer" className="font-semibold text-brand hover:underline">
                Open the official document at {c.pageLabel} ↗
              </a>
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
