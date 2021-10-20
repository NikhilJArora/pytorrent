def read_file(file_path: str, **kwargs) -> dict:
    if "mode" not in kwargs:
        kwargs["mode"] = "rb"
    with open(file_path, **kwargs) as source_file:
        return source_file.read()
