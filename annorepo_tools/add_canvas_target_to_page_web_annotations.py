#!/usr/bin/env python3

import argparse
import json
import os
import sys
from dataclasses import dataclass

import jsonpath_ng
from loguru import logger
from lxml import etree

XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

ITEMS_JPE = jsonpath_ng.parse("$.items[*]")
LABEL_JPE = jsonpath_ng.parse("$.label.en")
IMAGE_ID_JPE = jsonpath_ng.parse("$.items[*].items[*].body.id")


# ns = {
#     "tei": "http://www.tei-c.org/ns/1.0",
#     "xml": "http://www.w3.org/XML/1998/namespace"
# }


@dataclass
class TargetIds:
    image_id: str
    canvas_id: str


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Adds Canvas and Image targets to `Page` web annotations,"
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
    found = 0
    for line in sys.stdin:
        webannotation = json.loads(line)
        if 'body' not in webannotation:
            continue
        body = webannotation['body']
        if 'type' in body and body['type'] == "Page":
            pages += 1
            if 'xml:id' in body:
                pb_id = body['xml:id']
                if pb_id in target_ids:
                    targets = target_ids[pb_id]
                    new_targets = [
                        {
                            "type": "Canvas",
                            "source": targets.canvas_id
                        },
                        {
                            "type": "Image",
                            "source": targets.image_id
                        }
                    ]
                    if not isinstance(webannotation['target'], list):
                        webannotation['target'] = [webannotation['target']]
                    webannotation['target'] += new_targets
                    found += 1
        print(json.dumps(webannotation, ensure_ascii=False, indent=None))
    print(f"Added canvas targets for {found} of {pages} pages", file=sys.stderr)


def pass_as_is():
    for line in sys.stdin:
        print(line, end='')


def get_target_ids(tei_path: str, canvas_data: dict[str, TargetIds]) -> dict[str, TargetIds]:
    tree = etree.parse(tei_path)
    root = tree.getroot()

    image_labels = {}
    for surface in root.iter(f'{{{TEI_NS}}}surface'):
        surface_id = surface.get(XML_ID)
        graphic = surface.find(f'{{{TEI_NS}}}graphic')
        url = graphic.get('url')
        if url:
            image_labels[surface_id] = url
        else:
            logger.warning(f"No graphic url found for surface_id '{surface_id}'")
        for zone in surface.iter(f'{{{TEI_NS}}}zone'):
            zone_id = zone.get(XML_ID)
            image_labels[zone_id] = url

    metadata = {}
    for page in root.iter(f'{{{TEI_NS}}}pb'):
        page_id = page.get(XML_ID)
        surface_id = page.get('facs')[1:]
        image_label = image_labels.get(surface_id)
        if image_label:
            if image_label in canvas_data:
                metadata[page_id] = canvas_data[image_label]
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
        canvas_data[label] = TargetIds(canvas_id=canvas_id, image_id=image_id)
    return canvas_data


if __name__ == "__main__":
    main()

# canvas_target_with_selector = {
#     "@context": "https://ns.huc.knaw.nl/huc-di-tt.jsonld",
#     "source": "https://israelsletters.org/files/israels/static/manifests/letters/ii001.json/canvas/israels/pages/b8564V2008_vs_b",
#     "type": "Canvas",
#     "selector": [
#         {
#             "@context": "http://iiif.io/api/annex/openannotation/context.json",
#             "type": "iiif:ImageApiSelector",
#             "region": "0,0,8272,6200"
#         }
#     ]
# }
