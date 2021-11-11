import hashlib
import asyncio

from io import BytesIO
from pathlib import Path
from loguru import logger
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw

from .cut_string import get_cut_str

font_file = "./font/sarasa-mono-sc-semibold.ttf"
font = ImageFont.truetype(font_file, 22)
cache = Path("./cache/t2i")
cache.mkdir(exist_ok=True, parents=True)


async def create_image(text: str, cut=64) -> bytes:
    return await asyncio.to_thread(_cache, text, cut)


def _cache(text: str, cut: int) -> bytes:
    str_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    cache.joinpath(str_hash[:2]).mkdir(exist_ok=True)
    cache_file = cache.joinpath(f"{str_hash[:2]}", f"{str_hash}.jpg")
    if cache_file.exists():
        logger.info(f"T2I Cache hit: {str_hash}")
        return cache_file.read_bytes()
    else:
        cache_file.write_bytes(_create_image(text, cut))
        return cache_file.read_bytes()


def _create_image(text: str, cut: int) -> bytes:
    cut_str = "\n".join(get_cut_str(text, cut))
    textx, texty = font.getsize_multiline(cut_str)
    image = Image.new("RGB", (textx + 50, texty + 50), (242, 242, 242))
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), cut_str, font=font, fill=(31, 31, 33))
    image.save(
        imageio := BytesIO(),
        format="JPEG",
        quality=90,
        subsampling=2,
        qtables="web_high",
    )
    return imageio.getvalue()


async def delete_old_cache():
    cache_files = cache.glob("t2i/**/*.jpg")
    i = 0
    r = 0
    for cache_file in cache_files:
        i += 1
        if cache_file.stat().st_mtime < (
            (datetime.now() - timedelta(days=14)).timestamp()
        ):
            cache_file.unlink()
            try:
                cache_file.parent.rmdir()
            except OSError:
                pass
            r += 1
    return i, r
