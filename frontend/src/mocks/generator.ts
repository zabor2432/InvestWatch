import { RULES } from "../domain/rules";
import { SOURCES } from "../domain/labels";
import type { ModuleId, RuleVerdict, Source } from "../domain/types";
import type { RecordDto, RuleResultDto } from "../api/dto";

/** Deterministyczny PRNG (mulberry32): te same dane przy każdym starcie. */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FIRMS = ["Xelion Capital TFI S.A.", "Alior Brokerage Dom Maklerski", "Bossa Invest DM", "Forex Pro Polska Sp. z o.o.", "Eurotrader CFD S.A.", "Capitalis Securities", "Nordic Markets Poland", "Trade Republic PL"];
const INFLUENCERS = ["@krypto_kuba", "@inwestuj_z_ola", "@pieniadz_na_pieniadz", "@gielda_dla_kazdego", "@trader_marcin", "@wolnosc_finansowa_pl", "@zysk24", "@bogaty_w_30_lat"];
const SHADOW = ["Heritage Wealth Partners", "Polska Family Office Group", "Alpha Private Advisory", "Meridian Consulting Invest", "Smart Capital Doradztwo", "Elite Wealth Management PL", "Kapitał i Przyszłość"];
const DOMAINS = ["example-invest.pl", "inwestycje-pro.com", "wealth-advisory.pl", "tradehub.eu", "kapital-start.pl"];

const PHRASES = ["gwarantowany zysk", "doradztwo inwestycyjne", "indywidualna strategia dla Ciebie", "zarządzanie majątkiem rodzinnym", "bez ryzyka", "gwarancja zwrotu", "family office", "osobisty doradca inwestycyjny", "pewny dochód pasywny"];

const M1_TITLES = [
  "Nowy rok, nowy portfel: sprawdź ofertę brokera",
  "Moja przygoda z CFD, link w bio",
  "Jak zarobiłem 18% w miesiąc na platformie partnera",
  "Kod rabatowy na prowizje u brokera: współpraca",
  "Live: handluję na koncie demo i prawdziwym",
];
const M2_TITLES = [
  "Fundusz Akcji Polskich: 5 lat wzrostów",
  "Konto maklerskie bez prowizji: otwórz w 5 minut",
  "Obligacje korporacyjne: stały dochód co kwartał",
  "Portfel modelowy 2027: prognozowana stopa zwrotu 14%",
  "Handluj CFD na ropie z dźwignią 1:30",
];
const M3_TITLES = [
  "Prywatny doradca inwestycyjny dla Twojej rodziny",
  "Family office dla przedsiębiorców: pełna dyskrecja",
  "Wealth management bez progu wejścia",
  "Indywidualna strategia inwestycyjna, konsultacje 1:1",
  "Zarządzamy Twoim majątkiem. Gwarantujemy wyniki",
];

const pick = <T,>(r: () => number, arr: T[]): T => arr[Math.floor(r() * arr.length)];

function ruleResults(r: () => number, violating: boolean): RuleResultDto[] {
  return RULES.map((rule): RuleResultDto => {
    const p = r();
    let verdict: RuleVerdict;
    let score: number;
    if (p < 0.08) { verdict = "n/a"; score = 0; }
    else if (violating && p < 0.45) { verdict = "fail"; score = 0.7 + r() * 0.3; }
    else if (p < 0.62) { verdict = "uncertain"; score = 0.4 + r() * 0.3; }
    else { verdict = "pass"; score = r() * 0.3; }
    return {
      rule_id: rule.id,
      verdict,
      score: Number(score.toFixed(2)),
      note: verdict === "fail" ? "Ostrzeżenie nieobecne lub nieczytelne w analizowanym materiale." : verdict === "uncertain" ? "Wymaga weryfikacji przez analityka." : null,
    };
  });
}

export interface GenOptions {
  now: number;
  module?: ModuleId;
  forceHigh?: boolean;
}

export function makeRecord(r: () => number, n: number, opts: GenOptions): RecordDto {
  const module: ModuleId = opts.module ?? ((1 + Math.floor(r() * 3)) as ModuleId);
  const truth = r() < 0.45;
  // Symulacja modelu: pozytywy dostają wyższy score, ale rozkłady się nakładają.
  let score = truth ? 0.45 + r() * 0.55 : r() * 0.75;
  if (opts.forceHigh) score = 0.82 + r() * 0.18;
  score = Number(score.toFixed(2));
  const source: Source = module === 2 ? "WWW" : pick(r, SOURCES);
  const domain = pick(r, DOMAINS);
  const slug = Math.floor(r() * 1e6).toString(36);
  const detectedAt = new Date(opts.now - Math.floor(r() * 30 * 86400000)).toISOString();
  const base = { id: `rec-${String(n).padStart(4, "0")}`, module, detected_at: detectedAt, source, risk_score: score, status: "new" as const, ground_truth: opts.forceHigh ? true : truth };
  const hash = Array.from({ length: 16 }, () => Math.floor(r() * 16).toString(16)).join("");
  const evidence = [
    { kind: "snapshot" as const, label: "Archiwum treści", value: `snapshots/${base.id}.html` },
    { kind: "screenshot" as const, label: "Zrzut ekranu", value: `screens/${base.id}.png` },
    { kind: "hash" as const, label: "SHA-256 (skrót)", value: hash },
  ];

  if (module === 1) {
    const firm = pick(r, FIRMS);
    const who = pick(r, INFLUENCERS);
    return { ...base, url: `https://${source.toLowerCase()}.com/${who.slice(1)}/post/${slug}`, title: pick(r, M1_TITLES), content: `Post promujący ofertę ${firm}. Autor nie ujawnia charakteru współpracy, w opisie link afiliacyjny i hasło „zysk bez wysiłku”.`, entity: { name: who, kind: "finfluencer", url: `https://${source.toLowerCase()}.com/${who.slice(1)}` }, advertised_firm: firm, evidence };
  }
  if (module === 2) {
    const firm = pick(r, FIRMS);
    const violating = score >= 0.5;
    return { ...base, url: `https://www.${domain}/oferta/${slug}`, title: pick(r, M2_TITLES), content: `Materiał marketingowy ${firm}. Wyniki historyczne wyeksponowane nad treścią ostrzeżenia, informacja o ryzyku w stopce drobnym drukiem.`, entity: { name: firm, kind: "investment_firm", url: `https://www.${domain}` }, rule_results: ruleResults(r, violating), evidence };
  }
  const who = pick(r, SHADOW);
  const matched = [pick(r, PHRASES), pick(r, PHRASES)].filter((v, i, a) => a.indexOf(v) === i);
  return { ...base, url: `https://${domain}/uslugi/${slug}`, title: pick(r, M3_TITLES), content: `Oferta ${who}: usługi doradcze dla klientów w Polsce. Podmiot nie figuruje w rejestrze firm inwestycyjnych.`, entity: { name: who, kind: "unauthorized", url: `https://${domain}` }, matched_phrases: matched, evidence: [...evidence, ...matched.map((m) => ({ kind: "phrase" as const, label: "Wykryta fraza", value: m }))] };
}

export function seedRecords(count = 240, now = Date.now()): RecordDto[] {
  const r = rng(20261121);
  return Array.from({ length: count }, (_, i) => makeRecord(r, i + 1, { now })).sort((a, b) => b.detected_at.localeCompare(a.detected_at));
}
