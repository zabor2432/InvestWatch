# Scraper — TODO

## Dane o layoucie we wszystkich modułach (propozycja z 2026-11-22)

Dziś każda strona WWW we wszystkich modułach dostaje zrzuty pierwszego ekranu (desktop + mobile, PNG),
a tekstowe dane o layoucie (`posts.raw.layout`) zbiera tylko moduł 2 (`firm_marketing`).

Propozycja: zbierać `raw.layout` dla stron WWW we wszystkich modułach i z całej strony, nie tylko z pierwszego ekranu:

- bloki tekstu o ryzyku / zysku z rozmiarem i kolorem czcionki, tłem, pozycją i flagami `above_fold`, `in_footer`,
  `in_disclaimer`, `collapsed`, `in_link`; dominująca czcionka strony;
- dzięki temu model widzi, czy ostrzeżenie o ryzyku istnieje tylko niżej na stronie lub w stopce (reguła 6),
  a nie tylko to, co jest na zrzucie;
- koszt: jedno `page.evaluate` na wersję strony (strona i tak jest renderowana do zrzutów), kilkadziesiąt kB JSON na rekord.

Do zrobienia: w `app/collectors/web.py` przekazywać `with_layout=True` niezależnie od taska; opisać pola w README.
