import { useEffect, useRef, useState, type FormEvent } from 'react';
import { SchemeCard } from '../components/SchemeCard';
import { Button, Card, Choice, ErrorNote, Field, Input, Label, Select, Shell, YesNo } from '../components/ui';
import { api, ApiError, type MatchResponse } from '../lib/api';
import { emptyProfile, FLAGS, LEVELS, rupees, STATES, useProfile, type Profile } from '../lib/profile';

const num = (s: string) => (s.trim() === '' ? undefined : Number(s));

export function CheckPage() {
  const [p, setP] = useProfile();
  const [res, setRes] = useState<MatchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showNo, setShowNo] = useState(false);
  const resultsRef = useRef<HTMLDivElement>(null);
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP((old) => ({ ...old, [k]: v }));

  async function run(e?: FormEvent, scroll = true) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setRes(await api<MatchResponse>('/match', p));
      if (scroll) setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }
  // Show results straight away for a returning visitor.
  useEffect(() => {
    if (p.income !== undefined || p.level) void run(undefined, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const studying = p.level && p.level !== 'class_9_10' && p.level !== 'class_11_12';
  const yes = res?.results.filter((r) => r.verdict === 'eligible') ?? [];
  const maybe = res?.results.filter((r) => r.verdict === 'maybe') ?? [];
  const no = res?.results.filter((r) => r.verdict === 'not_eligible') ?? [];

  return (
    <Shell>
      <div className="grid gap-2">
        <h1 className="display text-4xl font-semibold">Which scholarships can I get?</h1>
        <p className="max-w-2xl text-muted">
          Answer what you know and skip the rest: blank answers never rule a scheme out, they show up as "check these".
          Your answers stay in this browser.
        </p>
      </div>

      <form onSubmit={run} className="mt-6 grid gap-6">
        <Card className="grid gap-5 p-5 sm:p-6">
          <Label>About you</Label>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="State or UT of domicile" htmlFor="state">
              <Select id="state" value={p.state ?? ''} onChange={(e) => set('state', e.target.value || undefined)}>
                <option value="">Select…</option>
                {STATES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
              </Select>
            </Field>
            <Field label="Age" htmlFor="age">
              <Input id="age" type="number" min={5} max={80} value={p.age ?? ''} onChange={(e) => set('age', num(e.target.value))} />
            </Field>
          </div>
          <Field label="Category">
            <Choice label="Category" value={p.category} onChange={(v) => set('category', v)}
              options={[['general', 'General'], ['ews', 'EWS'], ['obc', 'OBC'], ['ebc', 'EBC'], ['dnt', 'DNT'], ['sc', 'SC'], ['st', 'ST']]} />
          </Field>
          <Field label="Gender">
            <Choice label="Gender" value={p.gender} onChange={(v) => set('gender', v)}
              options={[['female', 'Female'], ['male', 'Male'], ['transgender', 'Transgender']]} />
          </Field>
          <Field label="Disability" hint="Many schemes need a certified disability of 40% or more.">
            <div className="flex flex-wrap items-center gap-3">
              <Choice label="Disability" value={p.disability_pct === undefined ? undefined : p.disability_pct > 0 ? 'yes' : 'no'}
                options={[['no', 'No disability'], ['yes', 'I have a disability']]}
                onChange={(v) => set('disability_pct', v === undefined ? undefined : v === 'no' ? 0 : p.disability_pct || 40)} />
              {p.disability_pct ? (
                <label className="flex items-center gap-2 text-sm">
                  <Input aria-label="Disability percentage" type="number" min={1} max={100} className="w-24"
                    value={p.disability_pct} onChange={(e) => set('disability_pct', num(e.target.value) ?? 40)} />
                  %
                </label>
              ) : null}
            </div>
          </Field>
        </Card>

        <Card className="grid gap-5 p-5 sm:p-6">
          <Label>Family income</Label>
          <Field label="Total family income in the last financial year (₹)" htmlFor="income"
            hint={p.income !== undefined ? `= ${rupees(p.income)} a year` : 'Income from all sources, as on your income certificate.'}>
            <Input id="income" type="number" inputMode="numeric" min={0} step={1000} value={p.income ?? ''}
              onChange={(e) => set('income', num(e.target.value))} />
          </Field>
          <div className="flex flex-wrap gap-2">
            {[100000, 250000, 350000, 450000, 800000].map((v) => (
              <button key={v} type="button" onClick={() => set('income', v)}
                className="rounded-full border border-line px-3 py-1 text-sm hover:border-muted">{rupees(v)}</button>
            ))}
          </div>
        </Card>

        <Card className="grid gap-5 p-5 sm:p-6">
          <Label>Your studies (this year or next)</Label>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Studying at" htmlFor="level">
              <Select id="level" value={p.level ?? ''} onChange={(e) => set('level', (e.target.value || undefined) as Profile['level'])}>
                <option value="">Select…</option>
                {LEVELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </Select>
            </Field>
            {studying ? (
              <Field label="Course type" htmlFor="ctype">
                <Select id="ctype" value={p.course_type ?? ''} onChange={(e) => set('course_type', (e.target.value || undefined) as Profile['course_type'])}>
                  <option value="">Select…</option>
                  <option value="technical">Engineering / technical / pharmacy (AICTE)</option>
                  <option value="mba_mca">MBA / MCA</option>
                  <option value="medical">Medical / dental / nursing</option>
                  <option value="general">Arts / science / commerce</option>
                  <option value="professional_other">Other professional (law, B.Ed, etc.)</option>
                </Select>
              </Field>
            ) : (
              <Field label="School type" htmlFor="school">
                <Select id="school" value={p.school_type ?? ''} onChange={(e) => set('school_type', (e.target.value || undefined) as Profile['school_type'])}>
                  <option value="">Select…</option>
                  <option value="government">Government school</option>
                  <option value="govt_aided">Government-aided school</option>
                  <option value="local_body">Local body school</option>
                  <option value="kv_jnv">Kendriya Vidyalaya / Navodaya</option>
                  <option value="private">Private school</option>
                </Select>
              </Field>
            )}
          </div>
          {studying ? (
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Regular (full-time) course?"><YesNo label="Regular course" value={p.study_mode === undefined ? undefined : p.study_mode === 'regular'} onChange={(v) => set('study_mode', v === undefined ? undefined : v ? 'regular' : 'distance')} /></Field>
              <Field label="At an IIT, IIM, NIT, IIIT, AIIMS, NIFT, NID or similar?"><YesNo label="Top institute" value={p.top_institution} onChange={(v) => set('top_institution', v)} /></Field>
              {p.level === 'pg' || p.level === 'phd' ? (
                <Field label="Studying abroad?"><YesNo label="Studying abroad" value={p.studying_abroad} onChange={(v) => set('studying_abroad', v)} /></Field>
              ) : null}
            </div>
          ) : null}
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Class 12 percentile in your board (if known)" htmlFor="pct" hint="CSSS needs above 80. Leave blank if unsure.">
              <Input id="pct" type="number" min={0} max={100} value={p.class12_percentile ?? ''} onChange={(e) => set('class12_percentile', num(e.target.value))} />
            </Field>
            <Field label="Marks % in your last qualifying exam" htmlFor="marks">
              <Input id="marks" type="number" min={0} max={100} value={p.qualifying_marks_pct ?? ''} onChange={(e) => set('qualifying_marks_pct', num(e.target.value))} />
            </Field>
          </div>
          <Field label="Already getting another scholarship or fee waiver?"><YesNo label="Other scholarship" value={p.other_scholarship} onChange={(v) => set('other_scholarship', v)} /></Field>
        </Card>

        <Card className="grid gap-4 p-5 sm:p-6">
          <Label>Special situations</Label>
          <div className="grid gap-2.5">
            {FLAGS.map(([f, text]) => (
              <label key={f} className="flex items-start gap-3">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--brand)]" checked={p.flags.includes(f)}
                  onChange={(e) => setP((o) => ({ ...o, flags_answered: true, flags: e.target.checked ? [...o.flags, f] : o.flags.filter((x) => x !== f) }))} />
                <span>{text}</span>
              </label>
            ))}
            <label className="flex items-start gap-3">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--brand)]" checked={p.flags_answered && p.flags.length === 0}
                onChange={(e) => setP((o) => ({ ...o, flags: [], flags_answered: e.target.checked }))} />
              <span>None of these</span>
            </label>
          </div>
        </Card>

        {error ? <ErrorNote>{error}</ErrorNote> : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" busy={busy} className="px-6 py-3 text-base">Find my scholarships</Button>
          <Button type="button" variant="ghost" onClick={() => { setP(emptyProfile); setRes(null); }}>Clear answers</Button>
        </div>
      </form>

      <div ref={resultsRef} className="scroll-mt-4">
        {res ? (
          <div className="mt-10 grid gap-8">
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <h2 className="display text-3xl font-semibold">Your matches</h2>
              <p className="text-muted">
                <b className="text-yes">{yes.length}</b> you qualify for · <b className="text-maybe">{maybe.length}</b> to check · {no.length} not a match
              </p>
            </div>
            {yes.length ? <Group title="You qualify">{yes.map((m) => <SchemeCard key={m.scheme.id} m={m} />)}</Group> : null}
            {maybe.length ? <Group title="You might qualify: check these">{maybe.map((m) => <SchemeCard key={m.scheme.id} m={m} />)}</Group> : null}
            {!yes.length && !maybe.length ? (
              <Card className="p-5"><p>None of the {res.results.length} schemes we track match these answers. Check the reasons below, or ask a question.</p></Card>
            ) : null}
            <div>
              <button type="button" className="font-semibold text-brand hover:underline" onClick={() => setShowNo((s) => !s)} aria-expanded={showNo}>
                {showNo ? 'Hide' : 'Show'} the {no.length} schemes that don't match, and why
              </button>
              {showNo ? <div className="mt-4 grid gap-4">{no.map((m) => <SchemeCard key={m.scheme.id} m={m} />)}</div> : null}
            </div>
            {res.closed.length ? (
              <Card className="p-5">
                <p className="font-bold">Not open right now</p>
                <ul className="mt-2 grid gap-2 text-[15px]">
                  {res.closed.map(({ scheme: s }) => (
                    <li key={s.id}><b>{s.short}</b> <span className="text-muted">({s.status})</span>: {s.statusNote}</li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </div>
        ) : null}
      </div>
    </Shell>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-4">
      <h3 className="text-lg font-bold">{title}</h3>
      {children}
    </section>
  );
}
