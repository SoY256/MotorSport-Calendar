from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "play_store"
OUT.mkdir(exist_ok=True)


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    source_ratio = image.width / image.height
    target_ratio = size[0] / size[1]
    if source_ratio > target_ratio:
        height = size[1]
        width = round(height * source_ratio)
    else:
        width = size[0]
        height = round(width / source_ratio)
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    left = (width - size[0]) // 2
    top = (height - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1]))


icon_source = ROOT / "assets" / "branding" / "secar-icon-1024.png"
icon = Image.open(icon_source).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
icon.save(OUT / "icon-512.png", "PNG", optimize=True)

generated = ROOT / "assets" / "branding" / "secar-feature-background.png"
feature = cover(Image.open(generated).convert("RGB"), (1024, 500))
feature = ImageEnhance.Contrast(feature).enhance(1.04)
draw = ImageDraw.Draw(feature)
font_path = Path("C:/Windows/Fonts/seguisb.ttf")
font = ImageFont.truetype(str(font_path), 98)
small = ImageFont.truetype(str(font_path), 27)
draw.text((70, 166), "SECAR", font=font, fill=(250, 252, 255), stroke_width=1, stroke_fill=(220, 228, 240))
draw.rounded_rectangle((72, 286, 250, 292), radius=3, fill=(242, 48, 48))
draw.text((72, 310), "MOTORSPORT. ONE PLACE.", font=small, fill=(190, 204, 222))
feature.save(OUT / "feature-graphic-1024x500.jpg", "JPEG", quality=94, optimize=True, progressive=True)

screenshots = ROOT / "test" / "play_store"
for source in sorted(screenshots.glob("*.png")):
    image = Image.open(source).convert("RGB")
    image = image.resize((1080, 1920), Image.Resampling.LANCZOS)
    image.save(OUT / f"screenshot-{source.stem}-1080x1920.jpg", "JPEG", quality=94, optimize=True, progressive=True)

print(f"Created Play Store assets in {OUT}")
