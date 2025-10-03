#!/usr/bin/env python

import argparse
import json
import sys
from typing import Optional
from collections import OrderedDict

# Note: This script covers a pretty specific use-case (see usage description) that sits between stam 's webannotation export and the upload to annorepo
#       it merges annotations that have been split between two text variants (original/normalized, or formerly known as logical/physical)

def set_target_type(webannotation: dict, target_type: str, length: Optional[int] = None) -> dict:
    if isinstance(webannotation['target'], list):
        for i, target in enumerate(webannotation['target']):
            if length is not None and i >= length:
                break
            if isinstance(target,str):
                webannotation['target'][i] = {
                    "type": target_type,
                    "source": target[12:]
                }
    else:
        raise TypeError("expected target list")
    return webannotation

def main():
    parser = argparse.ArgumentParser(description="Consolidate multiple webannotations, as produced by e.g. stam fromxml, by merging secondary ones into the primary one. This means that what were two annotations in the input, becomes one annotation with multiple targets in the output. This is intended for situations where the annotation body is identical. The script uses standard input and standard output (JSONL)")
    parser.add_argument("--new-type", action="store", type=str, help="The type of the web annotation body when a secondary annotation was found and merged into a primary one", default="NormalText")
    parser.add_argument("--original-type", action="store", type=str, help="The type of the web annotation body when no secondary annotation was found", default="OriginalText")
    parser.add_argument("--id-suffix", action="store", type=str, help="The ID suffix secondary annotations carry, when compared to the primary ID", default=".normal")
    args = parser.parse_args()

    passed = 0 
    webannotations = OrderedDict()
    for line in sys.stdin:
        webannotation = json.loads(line)
        if 'id' in webannotation:
            webannotations[webannotation['id']] = webannotation
        elif line:
            #id-less annotation, nothing to merge, output-as is (blank node) but use the new type
            passed += 1
            print(json.dumps(set_target_type(webannotation, args.new_type), ensure_ascii=False, indent=None))

    merged = 0
    skipped = 0
    potential = 0
    for id, webannotation in webannotations.items():
        if not id.endswith(args.id_suffix): #not a secondary suffix
            if id.endswith((".translation-source",".translation-target","-translated","-translationsource")) or ('body' in webannotation and 'https://w3id.org/stam/extensions/stam-translate/Translation' in webannotation['body']):
                #skip translation annotations
                skipped += 1
                continue
            try:
                #find the secondary annotation that we merge into the current (primary) one
                secondary_id = id + args.id_suffix
                secondary = webannotations[secondary_id]
            except KeyError:
                #no secondary, primary web annotation is already the normal text, call it NormalText
                passed += 1
                print(json.dumps(set_target_type(webannotation, args.new_type), ensure_ascii=False, indent=None))
                continue
            merged += 1
            original_length = len(webannotation['target'])
            for target in secondary['target']:
                if isinstance(target,str) and target not in webannotation['target']:
                    #add the normal text
                    webannotation['target'].append(
                        {
                            "type": args.new_type,
                            "source": target[12:]
                        })
            #what was there before will be original text
            webannotation = set_target_type(webannotation, args.original_type, original_length)
            print(json.dumps(webannotation, ensure_ascii=False, indent=None))
        else:
            potential +=  1

    print(f"Consolidated {merged} (out of {potential}) annotations, passed {passed}, skipped {skipped}",file=sys.stderr)

if __name__ == "__main__":
    main()
