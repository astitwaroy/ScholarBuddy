import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { SchemeCard } from '../components/SchemeCard';
import { Card, Input, Label, Shell, cx } from '../components/ui';
import { api, type CatalogDoc, type Scheme, type Status } from '../lib/api';

function useCatalog() {
  const [data, setData] = useState<{ schemes: Scheme[]; documents: CatalogDoc[] } | null>(null);
  useEffect(() => {
    api<{ schemes: Scheme[]; documents: CatalogDoc[] }>('/catalog').then(setData).catch(() => {});
  }, []);
  return data;
}

export function Home() {
  const cat = useCatalog();
  const [status, setStatus] = useState<Status | null>(null);
  useEffect(() => {
    api<Status>('/status').then(setStatus).catch(() => {});
  }, []);
  const active = cat?.schemes.filter((s) => s.status === 'active').length;

  return (
    <Shell wide>
      <section className="grid items-center gap-10 py-6 md:grid-cols-[1.15fr_0.85fr] md:py-12">
        <div className="grid gap-5">
          <h1 className="display text-4xl leading-[1.05] font-semibold sm:text-6xl">
            Find the scholarships you're entitled to, and the rule that proves it.
          </h1>
          <p className="max-w-xl text-lg text-muted">
            Government scholarships are spread across dozens of long PDFs. ScholarSathi checks your details against
            {active ? ` ${active}` : ''} central and state schemes and answers questions straight from the official
            guidelines, citing the clause and page every time.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/check" className="rounded-lg bg-brand px-5 py-3.5 font-semibold text-brand-ink hover:opacity-90">Check my eligibility</Link>
            <Link to="/ask" className="rounded-lg border border-line bg-card px-5 py-3.5 font-semibold hover:border-muted">Ask a question</Link>
          </div>
          <p className="text-sm text-muted">Free. No sign-up. Your answers stay on your device.</p>
        </div>

        {/* A sample answer, to show what "cited" means */}
        <Card className="grid gap-3 p-5">
          <Label>Example answer</Label>
          <p className="rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-paper">My family earns ₹4 lakh. Can I get the Central Sector Scholarship?</p>
          <p className="leading-relaxed">
            Yes, if your Class 12 marks are <mark>above the 80th percentile</mark> of your board in your stream
            <Ref n={1} />, the family income limit is <mark>₹4.5 lakh a year</mark> <Ref n={1} />, and you're in a
            regular degree course, not a diploma <Ref n={1} />. It pays <mark>₹12,000 a year</mark> during graduation <Ref n={2} />.
          </p>
          <div className="grid gap-1 border-t border-line pt-3 text-sm text-muted">
            <p><Ref n={1} /> PM-USP CSSS guidelines · Section 4, Eligibility</p>
            <p><Ref n={2} /> PM-USP CSSS guidelines · Section 5, Rate of scholarship</p>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 border-t border-line py-10 md:grid-cols-3">
        <Step n="1" title="Tell us about yourself">Category, family income, course, state and any special situation. Skip what you don't know.</Step>
        <Step n="2" title="See what you qualify for">Each scheme shows which rules you meet, which you don't, and what to check, each linked to its source clause.</Step>
        <Step n="3" title="Ask the documents">Ask in plain words. Answers quote the official guidelines; when the documents don't say, we tell you.</Step>
      </section>

      <section className="grid gap-3 border-t border-line py-10">
        <h2 className="display text-2xl font-semibold">How the answers stay honest</h2>
        <ul className="grid max-w-3xl gap-2 text-muted">
          <li><b className="text-ink">Retrieval first.</b> Your question is matched against passages from the official PDFs using both keyword and meaning-based search.</li>
          <li><b className="text-ink">Quote or don't say it.</b> The AI must quote the exact words it relied on. Quotes that don't appear in the source are thrown out, and you're warned.</li>
          <li><b className="text-ink">Rules are checked by code, not guessed.</b> Eligibility uses a rule engine built from the guidelines, so the "you qualify" verdict never depends on the AI.</li>
        </ul>
        {status ? (
          <p className="text-sm text-muted">
            Library right now: {status.documents.ok} documents indexed into {status.documents.chunks} passages
            {status.ingesting ? ' (indexing in progress)' : ''}{status.documents.no_text ? ` · ${status.documents.no_text} scanned PDFs skipped` : ''}.{' '}
            <Link to="/sources" className="underline">See every source</Link>
          </p>
        ) : null}
      </section>
    </Shell>
  );
}

function Ref({ n }: { n: number }) {
  return <span className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-sunken px-1 align-[2px] text-[11px] font-bold text-brand">{n}</span>;
}

function Step({ n, title, children }: { n: string; title: string; children: string }) {
  return (
    <div className="grid gap-1.5">
      <p className="display text-3xl font-semibold text-gold">{n}</p>
      <h3 className="font-bold">{title}</h3>
      <p className="text-muted">{children}</p>
    </div>
  );
}

export function SchemesPage() {
  const cat = useCatalog();
  const [q, setQ] = useState('');
  const list = useMemo(() => {
    const t = q.toLowerCase();
    return (cat?.schemes ?? []).filter((s) => !t || `${s.name} ${s.short} ${s.forWhom} ${s.ministry}`.toLowerCase().includes(t));
  }, [cat, q]);
  return (
    <Shell>
      <h1 className="display text-4xl font-semibold">All schemes</h1>
      <p className="mt-2 text-muted">Every scheme we track, with its rules and the official documents they come from.</p>
      <Input className="mt-5" aria-label="Filter schemes" placeholder="Filter: e.g. girls, disability, SC, AICTE, North East…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="mt-6 grid gap-4">
        {list.filter((s) => s.status === 'active').map((s) => <SchemeCard key={s.id} scheme={s} />)}
        {list.some((s) => s.status !== 'active') ? <h2 className="mt-4 text-lg font-bold">Paused or discontinued</h2> : null}
        {list.filter((s) => s.status !== 'active').map((s) => (
          <Card key={s.id} className="p-5">
            <p className="font-bold">{s.short} <span className="text-sm font-semibold text-no">({s.status})</span></p>
            <p className="text-muted">{s.statusNote}</p>
          </Card>
        ))}
      </div>
    </Shell>
  );
}

export function SchemePage() {
  const { id = '' } = useParams();
  const cat = useCatalog();
  const s = cat?.schemes.find((x) => x.id === id);
  if (!cat) return <Shell><p className="text-muted">Loading…</p></Shell>;
  if (!s) return <Shell><p>Scheme not found. <Link to="/schemes" className="underline">See all schemes</Link></p></Shell>;
  return (
    <Shell>
      <Link to="/schemes" className="text-sm font-semibold text-brand">← All schemes</Link>
      <h1 className="display mt-3 text-4xl font-semibold">{s.name}</h1>
      {s.status !== 'active' ? <p className="mt-3 rounded-lg bg-no/10 px-3 py-2 font-semibold text-no">{s.status === 'paused' ? 'Paused' : 'Discontinued'}: {s.statusNote}</p> : null}
      <div className="mt-6"><SchemeCard scheme={s} open /></div>
      <Card className="mt-6 p-5">
        <Label>Official documents</Label>
        <ul className="mt-3 grid gap-2">
          {s.documents.map((d) => (
            <li key={d.id}><a href={d.url} target="_blank" rel="noreferrer" className="font-semibold text-brand hover:underline">{d.title} ↗</a><span className="block text-sm text-muted">{d.version}</span></li>
          ))}
        </ul>
      </Card>
    </Shell>
  );
}

const DOC_STATUS: Record<string, [string, string]> = {
  ok: ['Indexed', 'text-yes'],
  no_text: ['Scanned image, no text', 'text-maybe'],
  failed: ['Could not download', 'text-no'],
  pending: ['Waiting', 'text-muted'],
};

export function SourcesPage() {
  const cat = useCatalog();
  const [status, setStatus] = useState<Status | null>(null);
  useEffect(() => {
    api<Status>('/status').then(setStatus).catch(() => {});
  }, []);
  const names = useMemo(() => Object.fromEntries((cat?.schemes ?? []).map((s) => [s.id, s.short])), [cat]);
  return (
    <Shell>
      <h1 className="display text-4xl font-semibold">Sources</h1>
      <p className="mt-2 max-w-2xl text-muted">
        Every answer comes from these documents. They're downloaded from official government websites, split into
        passages by section, and indexed for keyword and meaning-based search.
      </p>
      {status ? (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Documents indexed" value={status.documents.ok} />
          <Stat label="Passages" value={status.documents.chunks} />
          <Stat label="With embeddings" value={status.documents.embedded} />
          <Stat label="AI answers" value={status.llm ? 'On' : 'Off'} />
        </div>
      ) : null}
      <div className="mt-6 overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line text-muted">
            <tr><th className="px-4 py-3 font-semibold">Document</th><th className="px-4 py-3 font-semibold">Schemes</th><th className="px-4 py-3 font-semibold">Status</th><th className="px-4 py-3 text-right font-semibold">Pages</th><th className="px-4 py-3 text-right font-semibold">Passages</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(cat?.documents ?? []).map((d) => {
              const [label, color] = DOC_STATUS[d.status ?? 'pending'] ?? DOC_STATUS.pending!;
              return (
                <tr key={d.id} className="align-top">
                  <td className="px-4 py-3"><a href={d.url} target="_blank" rel="noreferrer" className="font-semibold text-brand hover:underline">{d.title}</a><span className="block text-xs text-muted">{d.version}</span></td>
                  <td className="px-4 py-3">{d.scheme_ids.map((s) => names[s] ?? s).join(', ')}</td>
                  <td className={cx('px-4 py-3 font-semibold', color)} title={d.error ?? undefined}>{label}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{d.pages ?? '–'}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{d.chunks ?? '–'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Card className="p-4">
      <Label>{label}</Label>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
    </Card>
  );
}
