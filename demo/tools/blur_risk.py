"""Tworzy wariant prawdziwej reklamy z zamazanym fragmentem (np. stopką z ostrzeżeniem o ryzyku).

  uv run --no-project --with pillow python demo/tools/blur_risk.py ZRZUT.png X0 Y0 X1 Y1 [PROMIEŃ]

Współrzędne w pikselach oryginału (lewy-górny i prawy-dolny róg zamazywanego prostokąta).
Wynik `<nazwa>-zamazane.<rozszerzenie>` i kopia oryginału lądują w demo/real/
(katalog poza gitem). Seed dodaje je jako dwa rekordy modułu 2: oryginał (label=False) i zamazany (label=True)."""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "real"


def main(src: str, x0: str, y0: str, x1: str, y1: str, radius: str = "9") -> None:
    path = Path(src)
    box = (int(x0), int(y0), int(x1), int(y1))
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.open(path).convert("RGB")
    blurred = img.copy()
    blurred.paste(img.crop(box).filter(ImageFilter.GaussianBlur(float(radius))), box[:2])
    shutil.copy(path, OUT / path.name)
    blurred.save(OUT / f"{path.stem}-zamazane{path.suffix}")
    print(f"zapisano w {OUT}: {path.name} oraz {path.stem}-zamazane{path.suffix}")


if __name__ == "__main__":
    main(*sys.argv[1:])
