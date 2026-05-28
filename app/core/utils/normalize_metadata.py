import re
import json
from app.core.utils.clean_value import clean_blob_metadata_value


def normalize_blob_metadata(data):
    output = {}

    for k, v in data.items():

        key = re.sub(
            r'[^a-zA-Z0-9_]',
            '_',
            k.lower()
        )

        if not key:
            continue

        if key[0].isdigit():
            key = f"m_{key}"

        if isinstance(v, (list, dict)):
            value = json.dumps(
                v,
                ensure_ascii=False
            )

        elif v is None:
            value = ""
        else:
            value = str(v)

        output[key] = clean_blob_metadata_value(value)[:8000]

    return output
