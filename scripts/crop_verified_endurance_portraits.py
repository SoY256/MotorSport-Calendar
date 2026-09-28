"""Create manually verified face crops for endurance drivers missing automation."""

from pathlib import Path
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".tmp" / "portrait-sources"
OUTPUT = ROOT / "assets" / "portraits" / "faces"

# Pixel boxes were checked against the named official source portraits. They
# intentionally include the complete head and a small shoulder margin.
CROPS = {
    "nico-mueller": ("nico-mueller.jpg", (430, 15, 1050, 635)),
    "nick-boulle": ("nick-boulle.png", (125, 0, 360, 235)),
}


def main() -> None:
    target = OUTPUT / "imsa"
    target.mkdir(parents=True, exist_ok=True)
    for slug, (filename, box) in CROPS.items():
        image = Image.open(SOURCE / filename).convert("RGB")
        face = image.crop(box).resize((320, 320), Image.Resampling.LANCZOS)
        face.save(target / f"{slug}.jpg", quality=94)
        print(target / f"{slug}.jpg")

    wec = OUTPUT / "wec"
    wec.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target / "ricky-taylor.jpg", wec / "ricky-taylor.jpg")
    print(wec / "ricky-taylor.jpg")


if __name__ == "__main__":
    main()
