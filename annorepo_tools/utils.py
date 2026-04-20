import json
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Any, List, Optional

import jsonpath_ng
from loguru import logger
from lxml import etree


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


XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

ITEMS_JPE = jsonpath_ng.parse("$.items[*]")
LABEL_JPE = jsonpath_ng.parse("$.label.en")
IMAGE_ID_JPE = jsonpath_ng.parse("$.items[*].items[*].body.id")
HEIGHT_JPE = jsonpath_ng.parse("$.items[*].items[*].body.height")
WIDTH_JPE = jsonpath_ng.parse("$.items[*].items[*].body.width")


@dataclass
class TargetIds:
    image_id: str
    canvas_id: str
    width: int
    height: int
    selectors: list[dict[str, str]] = field(default_factory=list)


def read_canvas_data(manifest_path: str) -> dict[str, TargetIds]:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    canvas_data = {}
    for i in ITEMS_JPE.find(manifest):
        canvas = i.value
        canvas_id = canvas["id"]
        label = LABEL_JPE.find(canvas)[0].value[0]
        image_id = IMAGE_ID_JPE.find(canvas)[0].value
        width = WIDTH_JPE.find(canvas)[0].value
        height = HEIGHT_JPE.find(canvas)[0].value
        canvas_data[label] = TargetIds(canvas_id=canvas_id, image_id=image_id, width=width, height=height)
    return canvas_data


def get_page_target_ids(tei_path: str, canvas_data: dict[str, TargetIds]) -> dict[str, TargetIds]:
    tree = etree.parse(tei_path)
    root = tree.getroot()
    image_labels, rotation, zone_ullr_box = extract_surface_info(root)

    metadata = {}
    for page in root.iter(f'{{{TEI_NS}}}pb'):
        page_id = page.get(XML_ID)
        if not page_id:
            logger.error(f"Missing xml:id in <pb>")
        surface_id = page.get('facs')[1:]
        image_label = image_labels.get(surface_id)
        bounding_box = zone_ullr_box.get(surface_id)
        zone_rotation = rotation.get(surface_id)
        if image_label:
            if image_label in canvas_data:
                target_ids = deepcopy(canvas_data[image_label])
                region = calculate_xywh(ullr=bounding_box, width=target_ids.width, height=target_ids.height)
                selector = image_api_selector(region, zone_rotation)
                if selector:
                    target_ids.selectors.append(selector)
                adjusted_image_id = customize_iiif_image_url(original_url=target_ids.image_id, region=region,
                                                             rotation=zone_rotation)
                target_ids.image_id = adjusted_image_id
                metadata[page_id] = target_ids
            else:
                logger.warning(
                    f"graphic url '{image_label}' in surface '{surface_id}' has no matching canvas in the manifest.")
        else:
            logger.warning(f"No image_label found for surface_id '{surface_id}'")
    return metadata


def get_figure_target_ids(tei_path: str, canvas_data: dict[str, TargetIds]) -> dict[str, TargetIds]:
    tree = etree.parse(tei_path)
    root = tree.getroot()
    image_labels, rotation, zone_ullr_box = extract_surface_info(root)

    metadata = {}
    for figure in root.iter(f'{{{TEI_NS}}}figure'):
        figure_id = figure.get(XML_ID)
        if not figure_id:
            logger.error(f"Missing xml:id in <figure>")
        if "facs" in figure.attrib:
            surface_id = figure.get('facs')[1:]
        else:
            surface_id = ""
            logger.error(f"Missing facs in <figure>")
        image_label = image_labels.get(surface_id)
        bounding_box = zone_ullr_box.get(surface_id)
        zone_rotation = rotation.get(surface_id)
        if image_label:
            if image_label in canvas_data:
                target_ids = deepcopy(canvas_data[image_label])
                region = calculate_xywh(ullr=bounding_box, width=target_ids.width, height=target_ids.height)
                selector = image_api_selector(region, zone_rotation)
                if selector:
                    target_ids.selectors.append(selector)
                adjusted_image_id = customize_iiif_image_url(original_url=target_ids.image_id, region=region,
                                                             rotation=zone_rotation)
                target_ids.image_id = adjusted_image_id
                metadata[figure_id] = target_ids
            else:
                logger.warning(
                    f"graphic url '{image_label}' in surface '{surface_id}' has no matching canvas in the manifest.")
        else:
            logger.warning(f"No image_label found for surface_id '{surface_id}'")
    return metadata


def extract_surface_info(root) -> tuple[dict[Any, Any], dict[Any, Any], dict[Any, Any]]:
    image_labels = {}
    zone_ullr_box = {}
    rotation = {}
    for surface in root.iter(f'{{{TEI_NS}}}surface'):
        surface_id = surface.get(XML_ID)
        graphic = surface.find(f'{{{TEI_NS}}}graphic')
        # url = os.path.splitext(graphic.get('url'))[0]  # remove file extension
        url = graphic.get('url')
        if url:
            image_labels[surface_id] = url
        else:
            logger.warning(f"No graphic url found for surface_id '{surface_id}'")
        rotation_value = surface.get('rotate')
        if rotation_value:
            rotation[surface_id] = int(rotation_value)
        for zone in surface.iter(f'{{{TEI_NS}}}zone'):
            zone_id = zone.get(XML_ID)
            image_labels[zone_id] = url
            ulx = zone.get('ulx')
            uly = zone.get('uly')
            lrx = zone.get('lrx')
            lry = zone.get('lry')
            if ulx:
                zone_ullr_box[zone_id] = [float(ulx), float(uly), float(lrx), float(lry)]
            rotation_value = zone.get('rotate')
            if rotation_value:
                rotation[zone_id] = int(rotation_value)
    return image_labels, rotation, zone_ullr_box


def pass_as_is():
    for line in sys.stdin:
        print(line, end='')
