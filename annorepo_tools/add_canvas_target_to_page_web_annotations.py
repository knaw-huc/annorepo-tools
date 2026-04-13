#!/usr/bin/env python3

import argparse
import json
import os
import sys
from copy import deepcopy
from dataclasses import dataclass, field

import jsonpath_ng
from loguru import logger
from lxml import etree
from more_itertools import unique_everseen

import annorepo_tools.utils as u

XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

ITEMS_JPE = jsonpath_ng.parse("$.items[*]")
LABEL_JPE = jsonpath_ng.parse("$.label.en")
IMAGE_ID_JPE = jsonpath_ng.parse("$.items[*].items[*].body.id")
HEIGHT_JPE = jsonpath_ng.parse("$.items[*].items[*].body.height")
WIDTH_JPE = jsonpath_ng.parse("$.items[*].items[*].body.width")


# ns = {
#     "tei": "http://www.tei-c.org/ns/1.0",
#     "xml": "http://www.w3.org/XML/1998/namespace"
# }


@dataclass
class TargetIds:
    image_id: str
    canvas_id: str
    width: int
    height: int
    selectors: list[dict[str, str]] = field(default_factory=list)


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Adds Canvas and Image targets to `Page` and `Letter` web annotations,"
                    " based on the manifest and the TEI file."
                    " Reads JSONL from standard input (one JSON-LD webannotation per line)")
    parser.add_argument("--manifest", action="store", type=str,
                        help="the IIIF manifest file",
                        required=True)
    parser.add_argument("--tei", action="store", type=str,
                        help="the TEI file",
                        required=True)
    parser.add_argument("--ignore-missing-manifest", action="store_true",
                        help="when the manifest is missing, just pass through the annotations as-is")
    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        if not args.ignore_missing_manifest:
            logger.error(f"The manifest file {args.manifest} does not exist, cannot add targets.")
        pass_as_is()
        exit(0)

    if not os.path.exists(args.tei):
        logger.error(f"The TEI file {args.manifest} does not exist, cannot add targets.")
        pass_as_is()
        exit(0)

    canvas_data = read_canvas_data(args.manifest)
    target_ids = get_target_ids(args.tei, canvas_data)

    pages = 0
    pages_found = 0
    letters_found = 0
    for line in sys.stdin:
        webannotation = json.loads(line)
        if 'body' not in webannotation:
            continue
        body = webannotation['body']
        if 'type' in body:
            if body['type'] == "Letter":
                letters_found += 1
                new_targets = []
                for t in target_ids.values():
                    canvas_target = {
                        "type": "Canvas",
                        "source": t.canvas_id
                    }
                    if t.selectors:
                        canvas_target["selector"] = t.selectors
                    new_targets.append(canvas_target)
                webannotation['target'] += unique_everseen(new_targets, key=tuple)
            elif body['type'] == "Page":
                pages += 1
                if 'xml:id' in body:
                    pb_id = body['xml:id']
                    if pb_id in target_ids:
                        targets = target_ids[pb_id]
                        canvas_target = {
                            "type": "Canvas",
                            "source": targets.canvas_id
                        }
                        if targets.selectors:
                            canvas_target["selector"] = targets.selectors
                        new_targets = [
                            canvas_target,
                            {
                                "type": "Image",
                                "source": targets.image_id
                            }
                        ]
                        if not isinstance(webannotation['target'], list):
                            webannotation['target'] = [webannotation['target']]
                        webannotation['target'] += new_targets
                        pages_found += 1
                else:
                    logger.error(f"missing xml:id in {body}")
        print(json.dumps(webannotation, ensure_ascii=False, indent=None))
    print(f"Added canvas targets for {pages_found} of {pages} page(s) and {letters_found} letter(s)", file=sys.stderr)


def pass_as_is():
    for line in sys.stdin:
        print(line, end='')


def get_target_ids(tei_path: str, canvas_data: dict[str, TargetIds]) -> dict[str, TargetIds]:
    tree = etree.parse(tei_path)
    root = tree.getroot()
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
                zone_ullr_box[zone_id] = [int(ulx), int(uly), int(lrx), int(lry)]
            rotation_value = zone.get('rotate')
            if rotation_value:
                rotation[zone_id] = int(rotation_value)

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
                region = u.calculate_xywh(ullr=bounding_box, width=target_ids.width, height=target_ids.height)
                selector = u.image_api_selector(region, zone_rotation)
                if selector:
                    target_ids.selectors.append(selector)
                adjusted_image_id = u.customize_iiif_image_url(original_url=target_ids.image_id, region=region,
                                                               rotation=zone_rotation)
                target_ids.image_id = adjusted_image_id
                metadata[page_id] = target_ids
            else:
                logger.warning(
                    f"graphic url '{image_label}' in surface '{surface_id}' has no matching canvas in the manifest.")
        else:
            logger.warning(f"No image_label found for surface_id '{surface_id}'")
    return metadata


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


if __name__ == "__main__":
    main()
