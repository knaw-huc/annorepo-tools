#!/usr/bin/env python3

import argparse
import json
import os
import sys

from icecream import ic
from loguru import logger

import annorepo_tools.utils as u


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Adds a iiif url to `Picture` web annotations,"
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
        u.pass_as_is()
        exit(0)

    if not os.path.exists(args.tei):
        logger.error(f"The TEI file {args.tei} does not exist, cannot add targets.")
        u.pass_as_is()
        exit(0)

    canvas_data = u.read_canvas_data(args.manifest)
    target_ids = u.get_figure_target_ids(args.tei, canvas_data)

    pictures = 0
    pictures_found = 0
    for line in sys.stdin:
        webannotation = json.loads(line)
        ic(webannotation)
        if 'body' not in webannotation:
            continue
        body = webannotation['body']
        if 'type' in body:
            if body['type'] == "Picture":
                pictures += 1
                figure_id = body["xml:id"]
                if figure_id in target_ids:
                    t = target_ids[figure_id]
                    body['url'] = t.image_id
                    pictures_found += 1
                else:
                    ic(target_ids)

        print(json.dumps(webannotation, ensure_ascii=False, indent=None))
    print(f"Added iiif url to {pictures_found} of {pictures} picture(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
