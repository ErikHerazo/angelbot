def clean_blob_metadata_value(value):    
    value = str(value)

    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\t", " ")

    value = value.encode(
        "ascii",
        "ignore"
    ).decode()

    return value.strip()
