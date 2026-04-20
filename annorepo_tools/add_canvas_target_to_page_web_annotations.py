#!/usr/bin/env python3

import argparse
import json
import os
import sys

from loguru import logger
from more_itertools import unique_everseen

import annorepo_tools.utils as u


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
        u.pass_as_is()
        exit(0)

    if not os.path.exists(args.tei):
        logger.error(f"The TEI file {args.tei} does not exist, cannot add targets.")
        u.pass_as_is()
        exit(0)

    canvas_data = u.read_canvas_data(args.manifest)
    target_ids = u.get_page_target_ids(args.tei, canvas_data)

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


if __name__ == "__main__":
    main()
