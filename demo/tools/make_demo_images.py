"""Generuje syntetyczne przykłady reklamy dla modułu 2 (fikcyjna firma i fikcyjny ambasador): ta sama reklama ze czytelną
stopką o ryzyku i z zamazaną stopką oraz jej wersje na telefon (stopka czytelna albo ucięta: przykład dla reguły 8).
Uruchomienie: uv run --no-project --with pillow python demo/tools/make_demo_images.py (wynik jest w repo, to jednorazowy skrypt)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "images"
FONTS = "/System/Library/Fonts/Supplemental/"
W, H = 1200, 630
FOOTER = (0, 540, W, H)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS + ("Arial Bold.ttf" if bold else "Arial.ttf"), size)


def ad() -> Image.Image:
    img = Image.new("RGB", (W, H), "#0b2a4a")
    d = ImageDraw.Draw(img)
    # sylwetka piłkarza (fikcyjny ambasador) z piłką
    d.ellipse((860, 110, 960, 210), fill="#d9a066")            # głowa
    d.rounded_rectangle((820, 215, 1000, 420), 40, fill="#c8102e")  # koszulka
    d.rectangle((835, 420, 985, 520), fill="#ffffff")           # spodenki
    d.ellipse((1010, 450, 1090, 530), fill="#f2f2f2", outline="#222", width=4)  # piłka
    d.text((60, 50), "Nordic Capital Brokers", font=font(34, True), fill="#7fd1ff")
    d.text((60, 130), "Inwestuj jak mistrz.", font=font(64, True), fill="#ffffff")
    d.text((60, 215), "Ambasador marki: Marcus Vålen", font=font(30), fill="#c9d6e2")
    d.text((60, 290), "+27%", font=font(150, True), fill="#3ddc84")
    d.text((60, 460), "średni zwrot naszych klientów w 2025 roku", font=font(28), fill="#ffffff")
    d.rounded_rectangle((60, 500, 330, 535), 8, fill="#3ddc84")
    d.text((80, 504), "OTWÓRZ KONTO", font=font(24, True), fill="#0b2a4a")
    # stopka z informacją o ryzyku
    d.rectangle(FOOTER, fill="#e9eef3")
    d.text((20, 548), "REKLAMA. Inwestowanie wiąże się z ryzykiem utraty kapitału. Wyniki historyczne nie są",
           font=font(19), fill="#101820")
    d.text((20, 575), "wiarygodnym wskaźnikiem przyszłych wyników. Instrumenty z dźwignią: ryzyko utraty "
           "całości wpłaconych środków.", font=font(19), fill="#101820")
    return img


MW, MH = 390, 760


def mobile(cut_footer: bool) -> Image.Image:
    """Ta sama reklama w układzie pionowym. Z `cut_footer` informacja o ryzyku wychodzi poza ekran (reguła 8)."""
    img = Image.new("RGB", (MW, MH), "#0b2a4a")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "Nordic Capital Brokers", font=font(22, True), fill="#7fd1ff")
    d.text((20, 90), "Inwestuj jak mistrz.", font=font(34, True), fill="#ffffff")
    d.text((20, 150), "Ambasador: Marcus Vålen", font=font(18), fill="#c9d6e2")
    d.text((20, 200), "+27%", font=font(110, True), fill="#3ddc84")
    d.text((20, 330), "średni zwrot naszych klientów w 2025 roku", font=font(16), fill="#ffffff")
    d.rounded_rectangle((20, 380, 230, 420), 8, fill="#3ddc84")
    d.text((38, 388), "OTWÓRZ KONTO", font=font(20, True), fill="#0b2a4a")
    top = 520 if not cut_footer else MH - 22  # ucięta stopka: widać tylko pierwszy wiersz przy krawędzi ekranu
    d.rectangle((0, top, MW, MH), fill="#e9eef3")
    lines = ["REKLAMA. Inwestowanie wiąże się z", "ryzykiem utraty kapitału. Wyniki", "historyczne nie są wiarygodnym", "wskaźnikiem przyszłych wyników.",
             "Instrumenty z dźwignią: ryzyko utraty", "całości wpłaconych środków."]
    for i, line in enumerate(lines):
        d.text((16, top + 10 + i * 24), line, font=font(17), fill="#101820")
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    clear = ad()
    clear.save(OUT / "reklama-ambasador.png")
    blurred = clear.copy()
    region = blurred.crop(FOOTER).filter(ImageFilter.GaussianBlur(9))
    blurred.paste(region, FOOTER[:2])
    blurred.save(OUT / "reklama-ambasador-zamazane-ryzyko.png")
    mobile(cut_footer=False).save(OUT / "reklama-ambasador-mobile.png")
    mobile(cut_footer=True).save(OUT / "reklama-ambasador-mobile-ucieta.png")


if __name__ == "__main__":
    main()
