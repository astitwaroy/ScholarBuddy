import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AnswerText, CitationList } from '../components/Citations';
import { Button, Card, ErrorNote, Label, Select, Shell } from '../components/ui';
import { api, ApiError, type AskResponse, type Scheme } from '../lib/api';
import { hasProfile, useProfile } from '../lib/profile';

interface Turn { q: string; schemeId: string | null; res?: AskResponse; error?: string }

const SUGGESTED = [
  'What is the income limit for the Central Sector Scholarship?',
  'Can a girl in B.Tech get the AICTE Pragati scholarship if her family earns 7 lakh?',
  'Is the single girl child scholarship for PG still available?',
  'Which schools are not eligible for NMMSS?',
  'Is the minority post-matric scholarship still running?',
  'What is the age limit for the National Overseas Scholarship?',
];

export function AskPage() {
  const [params, setParams] = useSearchParams();
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [schemeId, setSchemeId] = useState<string | null>(params.get('scheme'));
  const [q, setQ] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [profile] = useProfile();
  const [useMine, setUseMine] = useState(hasProfile(profile));
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<{ schemes: Scheme[] }>('/catalog').then((c) => setSchemes(c.schemes)).catch(() => {});
  }, []);

  async function ask(question: string) {
    const text = question.trim();
    if (text.length < 3 || busy) return;
    setBusy(true);
    setQ('');
    const turn: Turn = { q: text, schemeId };
    setTurns((t) => [...t, turn]);
    try {
      const res = await api<AskResponse>('/ask', { question: text, schemeId, profile: useMine ? profile : null });
      setTurns((t) => t.map((x) => (x === turn ? { ...x, res } : x)));
    } catch (e) {
      setTurns((t) => t.map((x) => (x === turn ? { ...x, error: (e as ApiError).message } : x)));
    } finally {
      setBusy(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }), 50);
    }
  }

  const scheme = schemes.find((s) => s.id === schemeId);

  return (
    <Shell>
      <div className="grid gap-2">
        <h1 className="display text-4xl font-semibold">Ask about a scholarship</h1>
        <p className="max-w-2xl text-muted">
          Answers come only from the official guideline documents, with the clause and page for every point. If the
          documents don't say, you'll be told.
        </p>
      </div>

      <div className="mt-6 grid gap-6">
        {turns.map((t, i) => <TurnView key={i} t={t} schemes={schemes} />)}
        {!turns.length ? (
          <div className="grid gap-2">
            <Label>Try one of these</Label>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED.map((s) => (
                <button key={s} type="button" onClick={() => ask(s)} className="rounded-full border border-line bg-card px-3.5 py-1.5 text-left text-sm hover:border-muted">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <div ref={endRef} />

        <form onSubmit={(e: FormEvent) => { e.preventDefault(); void ask(q); }} className="sticky bottom-3 grid gap-3 rounded-xl border border-line bg-card p-3 shadow-lg shadow-black/5">
          <textarea
            aria-label="Your question"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void ask(q); } }}
            rows={2}
            maxLength={500}
            placeholder={scheme ? `Ask about ${scheme.short}…` : 'e.g. My father earns 3 lakh. Can I get a scholarship for B.Sc?'}
            className="w-full resize-none rounded-lg border-0 bg-transparent px-2 py-1.5 text-[15px] focus:outline-none"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Select aria-label="Limit to a scheme" className="w-auto py-1.5 text-sm" value={schemeId ?? ''}
                onChange={(e) => { const v = e.target.value || null; setSchemeId(v); setParams(v ? { scheme: v } : {}); }}>
                <option value="">All schemes</option>
                {schemes.filter((s) => s.status === 'active').map((s) => <option key={s.id} value={s.id}>{s.short}</option>)}
              </Select>
              {hasProfile(profile) ? (
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={useMine} onChange={(e) => setUseMine(e.target.checked)} className="h-4 w-4 accent-[var(--brand)]" />
                  Use my answers from <Link to="/check" className="underline">Check eligibility</Link>
                </label>
              ) : null}
            </div>
            <Button type="submit" busy={busy} disabled={q.trim().length < 3}>Ask</Button>
          </div>
        </form>
      </div>
    </Shell>
  );
}

function TurnView({ t, schemes }: { t: Turn; schemes: Scheme[] }) {
  const [active, setActive] = useState<number | null>(null);
  const scope = schemes.find((s) => s.id === t.schemeId);
  return (
    <div className="grid gap-3">
      <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-paper">
        {t.q}
        {scope ? <span className="mt-1 block text-xs opacity-70">About: {scope.short}</span> : null}
      </div>
      <Card className="p-5">
        {t.error ? <ErrorNote>{t.error}</ErrorNote> : !t.res ? (
          <p className="text-muted">Reading the official guidelines…</p>
        ) : (
          <div className="grid gap-4">
            {t.res.warning ? <p className="rounded-lg bg-gold-soft px-3 py-2 text-sm">{t.res.warning}</p> : null}
            <AnswerText text={t.res.answer} citations={t.res.citations} active={active} setActive={setActive} />
            {t.res.citations.length ? (
              <div className="grid gap-2 border-t border-line pt-3">
                <Label>{t.res.found ? 'Sources' : 'Closest passages we found'}</Label>
                <CitationList citations={t.res.citations} active={active} setActive={setActive} />
              </div>
            ) : null}
            <p className="text-xs text-muted">
              {t.res.mode === 'llm'
                ? `Written by ${t.res.model ?? 'an AI model'} from the sources above${t.res.grounding ? ` · ${t.res.grounding.verified} of ${t.res.grounding.cited} citations matched word-for-word` : ''}.`
                : t.res.mode === 'extractive' ? 'Sentences taken directly from the official documents (AI answers are switched off).' : ''}
              {' '}Confirm on the official portal before applying.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
