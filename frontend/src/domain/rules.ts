export interface RuleDef {
  id: string;
  name: string;
  description: string;
  legalBasis: string;
}

const DEL = "rozporządzenia del. 2017/565";

/** Reguły 1-18 wg załącznika UKNF „kryteria oceny informacji o ryzyku”. */
export const RULES: RuleDef[] = [
  { id: "1", name: "Identyfikacja firmy", description: "Czy materiał zawiera oficjalną nazwę firmy inwestycyjnej.", legalBasis: `art. 44 ust. 2 lit. a ${DEL}` },
  { id: "2", name: "Oznaczenie reklamy", description: "Czy materiał reklamowy/promocyjny jest jednoznacznie oznaczony jako taki.", legalBasis: "art. 24 ust. 3 MiFID II" },
  { id: "3", name: "Informacja o ryzyku", description: "Czy twierdzeniom o potencjalnych zyskach bezpośrednio towarzyszy informacja o istotnym ryzyku.", legalBasis: `art. 44 ust. 2 lit. b ${DEL}` },
  { id: "4", name: "Rozmiar czcionki ryzyka", description: "Porównanie wielkości czcionki informacji o ryzyku z przeważającą czcionką materiału.", legalBasis: `art. 44 ust. 2 lit. c ${DEL}` },
  { id: "5", name: "Ekspozycja i kontrast ryzyka", description: "Kontrast, przesłonięcie przez inne elementy i czytelność informacji o ryzyku.", legalBasis: `art. 44 ust. 2 lit. c i e ${DEL}` },
  { id: "6", name: "Zakrywanie / ukrywanie ryzyka", description: "Ryzyko ukryte w przypisach, sekcji „Legal” lub miejscach o niskiej widoczności.", legalBasis: `art. 44 ust. 2 lit. e ${DEL}` },
  { id: "7", name: "Dostępność za 1 kliknięciem", description: "Czy wyświetlenie informacji o ryzyku wymaga rozwinięcia, kliknięcia lub przejścia na inną warstwę.", legalBasis: `art. 44 ust. 2 lit. b i e ${DEL}` },
  { id: "8", name: "Responsywność (różne urządzenia)", description: "Czy tekst o ryzyku nie jest ucinany lub skalowany poniżej czytelności na desktopie, tablecie i telefonie.", legalBasis: `art. 44 ust. 2 lit. g ${DEL}` },
  { id: "9", name: "Zrozumiałość dla grupy docelowej", description: "Czy ostrzeżenie o ryzyku jest zrozumiałe dla przeciętnego odbiorcy grupy docelowej.", legalBasis: `art. 44 ust. 2 lit. d ${DEL}` },
  { id: "10", name: "Spójność językowa", description: "Czy informacje o ryzyku nie są w innym języku niż główny przekaz.", legalBasis: `art. 44 ust. 2 lit. f ${DEL}` },
  { id: "11", name: "Porównania produktów / usług", description: "Wykrycie porównań, weryfikacja źródła i przyjętych założeń.", legalBasis: `art. 44 ust. 3 ${DEL}` },
  { id: "12a", name: "Wyniki historyczne: okres i zakres", description: "Okres ostatnich 5 lat, pełne okresy 12-miesięczne, wskazany okres referencyjny i źródło.", legalBasis: `art. 44 ust. 4 ${DEL}` },
  { id: "12b", name: "Wyniki historyczne: warunki i waluta", description: "Ostrzeżenie o wpływie kursów walut oraz wpływie prowizji, opłat i obciążeń.", legalBasis: `art. 44 ust. 4 ${DEL}` },
  { id: "13", name: "Dominacja wyników historycznych", description: "Czy wyniki historyczne nie są najbardziej wyeksponowanym elementem.", legalBasis: `art. 44 ust. 4 lit. a ${DEL}` },
  { id: "14", name: "Ostrzeżenie przy wynikach historycznych", description: "Czy jest wyraźne zastrzeżenie, że wyniki historyczne nie są wiarygodnym wskaźnikiem przyszłych wyników.", legalBasis: `art. 44 ust. 4 lit. d ${DEL}` },
  { id: "15", name: "Prognozy przyszłych wyników", description: "Rozpoznanie prognoz i sprawdzenie ostrzeżenia; wykrycie prognozy jest flagowane w raporcie.", legalBasis: `art. 44 ust. 6 ${DEL}` },
  { id: "16", name: "Informacja podatkowa", description: "Przy odwołaniu do traktowania podatkowego: zależność od sytuacji klienta i możliwość zmian.", legalBasis: `art. 44 ust. 7 ${DEL}` },
  { id: "17", name: "Zakaz sugerowania aprobaty organu nadzoru", description: "Odwołania do KNF / innego organu sugerujące zatwierdzenie lub aprobatę produktu.", legalBasis: `art. 44 ust. 8 ${DEL}` },
  { id: "18", name: "Nadzór jako argument bezpieczeństwa", description: "Odwołania do organu nadzoru sugerujące bezpieczeństwo inwestycji.", legalBasis: `art. 44 ust. 8 ${DEL}` },
];

export const RULES_BY_ID: Record<string, RuleDef> = Object.fromEntries(RULES.map((r) => [r.id, r]));
