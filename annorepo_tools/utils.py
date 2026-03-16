from itertools import zip_longest
from typing import Any, List, Optional


def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
    return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]


def percentage(percent: int, total: int) -> int:
    return round((float(percent) / 100) * float(total))


def calculate_xywh(ullr: Optional[list[int]], width: int, height: int) -> Optional[str]:
    if ullr is None:
        return None

    if len(ullr) != 4:
        raise TypeError("ullr must be of length 4")

    ulx, uly, lrx, lry = ullr
    ax1 = percentage(ulx, width)
    ay1 = percentage(uly, height)
    ax2 = percentage(lrx, width)
    ay2 = percentage(lry, height)
    x = str(ax1)
    y = str(ay1)
    w = str(ax2 - ax1)
    h = str(ay2 - ay1)
    return ",".join([x, y, w, h])


def image_api_selector(region: Optional[str] = None, rotation: Optional[int] = None) -> Optional[dict[str, Any]]:
    selector = {
        "@context": "http://iiif.io/api/annex/openannotation/context.json",
        "type": "iiif:ImageApiSelector",
    }
    if region:
        selector["region"] = region
    if rotation:
        selector["rotation"] = rotation
    if region or rotation:
        return selector
    return None


def customize_iiif_image_url(original_url: str, region: Optional[str] = None, rotation: Optional[int] = None) -> str:
    new_url = original_url
    if region:
        new_url = new_url.replace("/full/", f"/{region}/")
    if rotation:
        new_url = new_url.replace("/0/default", f"/{rotation}/default")
    return new_url
