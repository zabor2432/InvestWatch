"""Reguły modułu 2 (kryteria oceny informacji o ryzyku). Reguła 1 (nazwa firmy) pominięta z założenia.

Każda reguła to pytanie "czy materiał NARUSZA wymóg" z kryteriami dla modelu decyzyjnego:
`bad` = kiedy odpowiedź to TAK (naruszenie, z przykładami), `good` = kiedy NIE.
"""

RULES = {
    "2": (
        "Oznaczenie reklamy",
        "Materiał jest promocją produktu/usługi finansowej i NIE jest jednoznacznie oznaczony jako reklama "
        "(brak napisu typu „REKLAMA”, „materiał reklamowy”, #reklama).",
        "Jest wyraźne oznaczenie reklamy albo materiał nie jest promocją.",
    ),
    "3": (
        "Informacja o ryzyku",
        "Są twierdzenia o zyskach lub zwrotach (np. „+27%”, „zarabiaj do 20%”), a bezpośrednio przy nich "
        "NIE ma informacji o ryzyku utraty kapitału.",
        "Przy twierdzeniach o zyskach jest informacja o ryzyku albo materiał nie obiecuje zysków.",
    ),
    "4": (
        "Rozmiar czcionki ryzyka",
        "Informacja o ryzyku jest zapisana wyraźnie mniejszą czcionką niż reszta materiału (drobny druk).",
        "Czcionka informacji o ryzyku jest porównywalna z resztą tekstu albo ryzyka nie dotyczy.",
    ),
    "5": (
        "Ekspozycja i kontrast ryzyka",
        "Informacja o ryzyku jest nieczytelna: niski kontrast, zamazana, przesłonięta lub poza widocznym "
        "obszarem.",
        "Informacja o ryzyku jest wyraźna, kontrastowa i nieprzesłonięta albo ryzyka nie dotyczy.",
    ),
    "6": (
        "Zakrywanie / ukrywanie ryzyka",
        "Informacja o ryzyku jest ukryta: tylko w przypisie, w sekcji „Legal”, na dole strony lub w miejscu "
        "o niskiej widoczności, albo zamazana.",
        "Informacja o ryzyku jest widoczna na równi z przekazem reklamowym.",
    ),
    "7": (
        "Dostępność za 1 kliknięciem",
        "Aby zobaczyć informację o ryzyku, trzeba coś rozwinąć, kliknąć link lub przejść na inną stronę.",
        "Informacja o ryzyku jest widoczna od razu w materiale.",
    ),
    "8": (
        "Responsywność",
        "Tekst o ryzyku jest ucięty albo za mały, żeby przeczytać go na ekranie telefonu lub tabletu.",
        "Tekst o ryzyku jest czytelny na ekranach różnej wielkości.",
    ),
    "9": (
        "Zrozumiałość dla grupy docelowej",
        "Ostrzeżenie o ryzyku jest napisane trudnym żargonem lub niejasno, niezrozumiale dla zwykłego "
        "odbiorcy.",
        "Ostrzeżenie jest proste i zrozumiałe albo go nie wymagano.",
    ),
    "10": (
        "Spójność językowa",
        "Informacja o ryzyku jest w innym języku niż główny przekaz (np. po angielsku w polskiej reklamie).",
        "Informacja o ryzyku jest w tym samym języku co reszta materiału.",
    ),
    "11": (
        "Porównania produktów i usług",
        "Materiał porównuje produkty lub usługi (np. „taniej niż konkurencja”) bez wskazania źródła "
        "i założeń porównania.",
        "Brak porównań albo podano źródło i założenia.",
    ),
    "12a": (
        "Wyniki historyczne: okres i zakres",
        "Pokazuje wyniki historyczne, ale bez okresu referencyjnego i źródła, za krótki okres (poniżej 5 lat) "
        "lub niepełne okresy 12-miesięczne.",
        "Brak wyników historycznych albo okres, zakres i źródło są podane poprawnie.",
    ),
    "12b": (
        "Wyniki historyczne: warunki i waluta",
        "Pokazuje wyniki historyczne bez ostrzeżenia o wpływie kursów walut oraz prowizji, opłat "
        "i obciążeń.",
        "Brak wyników historycznych albo podano wpływ kursów walut i kosztów.",
    ),
    "13": (
        "Dominacja wyników historycznych",
        "Wyniki historyczne lub obiecywany zwrot są najbardziej wyeksponowanym elementem materiału "
        "(największa czcionka, centralne miejsce), znacznie bardziej niż ostrzeżenie o ryzyku.",
        "Wyniki historyczne nie dominują nad resztą informacji albo ich nie ma.",
    ),
    "14": (
        "Ostrzeżenie przy wynikach historycznych",
        "Są wyniki historyczne, ale brak zastrzeżenia, że nie są wiarygodnym wskaźnikiem przyszłych wyników.",
        "Jest takie zastrzeżenie albo nie ma wyników historycznych.",
    ),
    "15": (
        "Prognozy przyszłych wyników",
        "Są prognozy przyszłych wyników („prognozujemy 12%”) bez ostrzeżenia, że prognoza nie jest "
        "wiarygodnym wskaźnikiem przyszłych wyników.",
        "Brak prognoz albo prognoza jest opatrzona takim ostrzeżeniem.",
    ),
    "16": (
        "Informacja podatkowa",
        "Materiał odwołuje się do traktowania podatkowego, ale bez informacji, że zależy ono od sytuacji "
        "klienta i może się zmienić.",
        "Brak odwołań do podatków albo jest zastrzeżenie o indywidualnej sytuacji i zmianach.",
    ),
    "17": (
        "Sugerowanie aprobaty organu nadzoru",
        "Powołuje się na KNF lub inny organ w sposób sugerujący zatwierdzenie lub aprobatę produktu "
        "(np. „zatwierdzone przez KNF”).",
        "Brak odwołań do organu nadzoru albo jest czysto informacyjne (numer zezwolenia).",
    ),
    "18": (
        "Nadzór jako argument bezpieczeństwa",
        "Powołuje się na nadzór jako dowód bezpieczeństwa inwestycji (np. „w pełni bezpieczne, bo "
        "nadzoruje nas KNF”).",
        "Brak takich odwołań.",
    ),
}

# Reguły wizualne: oceniane tylko z obrazem, osobnym przebiegiem i konkretnymi pytaniami o to, co widać
# (abstrakcyjne "czy narusza wymóg X" nie działało: model oceniał ~0 nawet dla nieczytelnej stopki).
# Reguła 8 (responsywność) wymaga pary obrazów tej samej reklamy: komputer i telefon; bez pary jest "nie dotyczy".
VISUAL = {"4", "5", "6", "8"}
FOOTER_ONLY = (
    "5",
    "6",
)  # oceniane na samym wycinku stopki; reguła 4 porównuje wielkość tekstu, więc dostaje też całość
VISUAL_QUESTIONS = {
    "4": {
        "instructions": "Czy tekst z informacją o ryzyku (ostrzeżenie o ryzyku inwestycyjnym) jest zapisany wyraźnie "
        "mniejszą czcionką niż nagłówki i reszta materiału?",
        "criteria": {
            "true": "Tak, informacja o ryzyku to drobny druk w porównaniu z resztą.",
            "false": "Nie, jest porównywalna z resztą tekstu.",
        },
    },
    "5": {
        "instructions": "Czy tekst z informacją o ryzyku jest trudny do odczytania z powodu niskiego kontrastu "
        "względem tła, rozmycia lub zlewania się z tłem?",
        "criteria": {
            "true": "Tak, tekst zlewa się z tłem lub jest rozmyty i trudno go przeczytać.",
            "false": "Nie, tekst jest wyraźny i kontrastowy.",
        },
    },
    "6": {
        "instructions": "Czy informacja o ryzyku jest ukryta lub łatwa do przeoczenia (mały druk na dole, kolor "
        "zbliżony do tła)?",
        "criteria": {"true": "Tak, łatwo ją przeoczyć.", "false": "Nie, jest dobrze widoczna."},
    },
    "8": {
        "instructions": "Porównaj obraz 1 (reklama na komputerze) z obrazem 2 (ta sama reklama na telefonie). "
        "Czy na telefonie informacja o ryzyku jest ucięta, zasłonięta albo wyraźnie mniej czytelna niż na komputerze?",
        "criteria": {
            "true": "Tak: na telefonie tekst o ryzyku jest ucięty, wychodzi poza ekran, jest zasłonięty albo znacznie "
            "mniejszy i trudniejszy do odczytania niż na komputerze.",
            "false": "Nie: na telefonie informacja o ryzyku jest w całości widoczna i porównywalnie czytelna.",
        },
    },
}

# Opis operacyjny z załącznika UKNF ("kryteria oceny informacji o ryzyku"), wysyłany modelowi w pytaniu
SPEC = {
    "2": "Czy materiał reklamowy/promocyjny jest jednoznacznie oznaczony jako taki.",
    "3": "Twierdzenia o potencjalnych zyskach muszą mieć bezpośrednio przy sobie informację o istotnym ryzyku.",
    "4": "Wielkość czcionki informacji o ryzyku względem przeważającej wielkości czcionki materiału.",
    "5": "Umiejscowienie informacji o ryzyku pod kątem kontrastu, przesłonięcia przez inne elementy oraz czytelności.",
    "6": "Ryzyko ukryte w przypisach, sekcji „Legal” lub w miejscach o niskiej widoczności.",
    "7": "Wyświetlenie informacji o ryzyku wymaga rozwinięcia, kliknięcia linku lub przejścia na inną warstwę.",
    "8": "Tekst nie jest ucinany ani skalowany poniżej czytelności na ekranach o różnych wielkościach.",
    "9": "Ostrzeżenie o ryzyku jest przedstawione językiem zrozumiałym dla przeciętnego odbiorcy grupy docelowej.",
    "10": "Informacje o ryzyku nie są podane w innym języku niż główny przekaz materiału.",
    "11": "Porównania produktów i usług muszą mieć wskazane źródło informacji i przyjęte założenia.",
    "12a": "Wyniki historyczne obejmują ostatnie 5 lat, pełne okresy 12-miesięczne, wskazany okres referencyjny i źródło.",
    "12b": "Jest ostrzeżenie o wpływie kursów walut oraz wskazany wpływ prowizji, opłat i obciążeń na wyniki.",
    "13": "Wyniki historyczne nie mogą być najbardziej wyeksponowanym elementem informacji.",
    "14": "Jest wyraźne zastrzeżenie, że wyniki historyczne nie są wiarygodnym wskaźnikiem przyszłych wyników.",
    "15": "Prognozy przyszłych wyników muszą mieć ostrzeżenie, że prognoza nie jest wiarygodnym wskaźnikiem.",
    "16": "Odwołanie do traktowania podatkowego wymaga informacji o zależności od sytuacji klienta i możliwości zmian.",
    "17": "Odwołania do KNF lub innego organu nie mogą sugerować zatwierdzenia ani aprobaty produktu/usługi.",
    "18": "Odwołania do organu nadzoru nie mogą sugerować bezpieczeństwa inwestycji.",
}
