from itertools import zip_longest
from typing import Any, List

def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
    return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]
