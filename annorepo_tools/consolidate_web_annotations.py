#!/usr/bin/env python

import argparse
import json
import sys
import glob
from typing import Optional, Any
from collections import OrderedDict
from copy import deepcopy

# Note: This script covers a pretty specific use-case (see usage description) that sits between stam 's webannotation export and the upload to annorepo
#       it merges annotations that have been split between two text variants (original/normalized, or formerly known as logical/physical)
#    
#       additionally, it embeds old-style entities from the apparatus in the webannotations (via the `tei:ref` property). This is only temporary for backward compatibility

def set_target_type(webannotation: dict, target_type: str, length: Optional[int] = None) -> dict:
    if isinstance(webannotation['target'], list):
        for i, target in enumerate(webannotation['target']):
            if length is not None and i >= length:
                break
            if isinstance(target,str):
                webannotation['target'][i] = {
                    "type": target_type,
                    "source": target
                }
            elif isinstance(target,dict) and 'source' in target:
                target['type'] = target_type
    elif isinstance(webannotation['target'], dict) and 'source' in webannotation['target']:
        webannotation['target'] = {
            "type": target_type,
            "source": webannotation['target']['source']
        }
    return webannotation


#(function by Bram migrated here from un-t-ann-gle)
def load_entities(path: str) -> dict[str, dict[str, Any]]:
    """Load entities from the apparatus"""
    entity_index = {}
    for data_path in glob.glob(f"{path}/*-entity-dict.json"):
        #logger.info(f"<= {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            entity_index.update(json.load(f))
    for k, v in entity_index.items():
        if "relation" in v and "ref" in v["relation"]:
            original_ref = v["relation"]["ref"]
            ref_key = original_ref.replace(".xml#", "/")
            if ref_key in entity_index:
                entity_index[k]["relation"]["ref"] = entity_index[ref_key]
            else:
                print(f"WARNING: {k.replace('/', '.xml#')}: no entity found for ref=\"{original_ref}\"",file=sys.stderr)
        entity_index[k] = rename_entity_type_fields(v)
    return entity_index

#(function by Bram migrated here from un-t-ann-gle)
def rename_entity_type_fields(d):
    if isinstance(d, dict):
        new_dict = {}
        for key, value in d.items():
            new_key = "tei:type" if key == "type" else key
            new_dict[new_key] = rename_entity_type_fields(value)
        return new_dict
    elif isinstance(d, list):
        return [rename_entity_type_fields(item) for item in d]
    else:
        return d

#(function by Bram migrated here from un-t-ann-gle)
def ref_to_entity(entity_index: dict[str, dict[str, Any]], ref: str) -> dict[str, Any]:
    key = ref.replace('.xml#', '/')
    if key in entity_index:
        return entity_index[key]
    else:
        print(f"WARNING: no entity found for reference {ref}", file=sys.stderr)
        return {ref: None}

def resolve_refs(data: dict[str,Any], entity_index: dict[str, dict[str, Any]]) -> int:
    #modifies dict in-place
    entities = 0
    for key, value in data.items():
        if key == "tei:ref" and isinstance(value, str):
            entities += 1
            data['tei:ref'] = ref_to_entity(entity_index, value)
        elif isinstance(value, dict):
            entities += resolve_refs(value, entity_index)
    return entities


def main():
    parser = argparse.ArgumentParser(description="Consolidate multiple webannotations, as produced by e.g. stam fromxml, by merging secondary ones into the primary one. This means that what were two annotations in the input, becomes one annotation with multiple targets in the output. This is intended for situations where the annotation body is identical. The script uses standard input and standard output (JSONL). Note that only annotations with identifiers can be merged (with their counterparts carrying a certain ID suffix)! All web annotations passed must describe the same resource")
    parser.add_argument("--new-type", action="store", type=str, help="The type of the web annotation body when a secondary annotation was found and merged into a primary one", default="NormalText")
    parser.add_argument("--original-type", action="store", type=str, help="The type of the web annotation body when no secondary annotation was found", default="OriginalText")
    parser.add_argument("--id-suffix", action="store", type=str, help="The ID suffix secondary annotations carry, when compared to the primary ID", default=".normal")
    parser.add_argument("--apparatus-dir", action="store", type=str, help="Directory containing apparatus JSON files. These will be embedded in the web annotations whenever there is an occurrence of `tei:ref`. This is only a TEMPORARY measure for backward compatibility, it results in invalid/unformalised linked data!")
    parser.add_argument("--body-id-prefix", action="store", type=str, help="Generate body IDs when absent, using the following prefix followed by a sequence number")
    parser.add_argument("--no-pass", action="store_true", help="Ignore all annotations without IDs, do not pass them through")
    args = parser.parse_args()

    entity_index = {}
    if 'apparatus_dir' in args:
        entity_index = load_entities(args.apparatus_dir)

    passed = 0 
    entities = 0
    webannotations = OrderedDict()
    pass_annotations = []
    body_count = 0
    has_secondary = False
    skipped = 0
    for line in sys.stdin:
        webannotation = json.loads(line)
        if 'body_id_prefix' in args and 'body' in webannotation and 'id' not in webannotation['body']:
            body_count += 1
            webannotation['body']['id']  = args.body_id_prefix + str(body_count)
        if 'id' in webannotation:
            id = webannotation['id']
            webannotations[id] = webannotation
            has_secondary = has_secondary or id.endswith(args.id_suffix) #a secondary suffix
        elif line:
            #id-less annotation, nothing to merge
            if args.no_pass:
                skipped += 1
            else:
                pass_annotations.append(webannotation)

    merged = 0
    potential = 0
    for id, webannotation in webannotations.items():
        if not id.endswith(args.id_suffix): #not a secondary suffix
            if id.endswith((".translation-source",".translation-target","-translated","-translationsource")) or ('body' in webannotation and 'https://w3id.org/stam/extensions/stam-translate/Translation' in webannotation['body']):
                #skip translation annotations
                skipped += 1
                continue
            try:
                #find the secondary (e.g. normalized) annotation that we merge into the current (primary) one
                secondary_id = id + args.id_suffix
                secondary = webannotations[secondary_id]
            except KeyError:
                #no secondary, primary web annotation is already the normal text, call it NormalText
                passed += 1
                if entity_index:
                    entities += resolve_refs(webannotation, entity_index)
                print(json.dumps(set_target_type(webannotation, args.new_type), ensure_ascii=False, indent=None))
                continue
            merged += 1
            original_length = len(webannotation['target'])
            for target in secondary['target']:
                if isinstance(target,str) and target not in webannotation['target']:
                    #add the normalized text
                    webannotation['target'].append(
                        {
                            "type": args.new_type,
                            "source": target
                        })
                elif isinstance(target,dict) and 'selector' in target and target not in webannotation['target']:
                    newtarget = deepcopy(target)
                    newtarget['type'] = args.new_type
                    webannotation['target'].append(newtarget)

            #what was there before will be original text
            webannotation = set_target_type(webannotation, args.original_type, original_length)
            if entity_index:
                entities += resolve_refs(webannotation, entity_index)
            print(json.dumps(webannotation, ensure_ascii=False, indent=None))
        else:
            potential +=  1

    #we output id-less annotations as-is (blank nodes)
    for webannotation in pass_annotations:
        #they either have the original type (if a distinction exist in the data), or new type (if there is no such distinction)
        webannotation = set_target_type(webannotation, args.original_type if has_secondary else args.new_type)
        if entity_index:
            entities += resolve_refs(webannotation, entity_index)
        print(json.dumps(webannotation, ensure_ascii=False, indent=None))

    if entity_index:
        print(f"Resolved {entities} entities ({len(entity_index)} loaded)",file=sys.stderr)
    print(f"Consolidated {merged} (out of {potential}) annotations, passed {len(pass_annotations)}, skipped {skipped}",file=sys.stderr)

if __name__ == "__main__":
    main()
