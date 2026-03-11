import argparse
import json
import os
import sys
from typing import Generator

PAGE_METADATA = 'pageMetadata'
TRANSCRIPTION_PLACEHOLDER = 'transcriptionPlaceholder'


def main():
    parser = argparse.ArgumentParser(
        description="Adds scan information to web annotations. Reads JSONL from standard input (one JSON-LD webannotation per line)")
    parser.add_argument("--metadata", action="store", type=str,
                        help=(
                            f"JSON file with metadata, should contain the key '{PAGE_METADATA}', with 'iiifBaseUrl' and 'manifestUrl' for each page (and optional '{TRANSCRIPTION_PLACEHOLDER}' for pages without transcription), both mapping Pages to URLs (via schema:identifier, @id or schema:image/schema:url)"),
                        required=True)
    parser.add_argument("--delete", action="store_true",
                        help="Remove image information from the body after moving it to the targets")
    args = parser.parse_args()

    with open(args.metadata, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    if not (PAGE_METADATA in metadata and isinstance(metadata[PAGE_METADATA], dict)):
        print(f"ERROR: Missing '{PAGE_METADATA}' key in metadata file {args.metadata}", file=sys.stderr)
        sys.exit(2)

    pages = 0
    found = 0
    for line in sys.stdin:
        webannotation = json.loads(line)
        if 'body' not in webannotation:
            continue
        body = webannotation['body']
        if 'type' in body and body['type'] == "Page":
            pages += 1
            if 'image' in body and isinstance(body['image'], dict) and 'url' in body['image']:
                for input_url in key_variants(body['image']['url']):
                    if input_url in metadata[PAGE_METADATA]:
                        page_metadata = metadata[PAGE_METADATA][input_url]
                        base_url = page_metadata['iiifBaseUrl']
                        manifest_url = page_metadata['manifestUrl']
                        if TRANSCRIPTION_PLACEHOLDER in page_metadata:
                            body[TRANSCRIPTION_PLACEHOLDER] = page_metadata[TRANSCRIPTION_PLACEHOLDER]
                        # MAYBE TODO: for later when we want to add dimension information (width,height is already present in the input)
                        # top = 0
                        # left = 0
                        # if 'top' in body['image'] and 'left' in body['image']:
                        #    #NOTE: these are not defined by schema.org!
                        #    top = int(body['image']['top'])
                        #    left = int(body['image']['left'])
                        # if 'width' in body['image'] and 'height' in body['image']:
                        #    width = int(body['image']['width'])
                        #    height = int(body['image']['height'])
                        new_targets = [
                            {
                                "type": "Canvas",
                                "source": manifest_url
                            },
                            {
                                "type": "Image",
                                "source": f"{base_url}/full/max/0/default.jpg"
                            }
                        ]
                        if not isinstance(webannotation['target'], list):
                            webannotation['target'] = [webannotation['target']]
                        webannotation['target'] += new_targets
                        found += 1
                        if args.delete:
                            del body['image']
                        break
        print(json.dumps(webannotation, ensure_ascii=False, indent=None))
    print(f"Added scans for {found} of {pages} pages", file=sys.stderr)


def key_variants(input_url: str) -> Generator[str, None, None]:
    yield input_url
    noext = ".".join(input_url.split(".")[0:-1])
    if noext:
        yield noext
    yield os.path.basename(input_url)


if __name__ == "__main__":
    main()
