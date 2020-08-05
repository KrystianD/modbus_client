import os

script_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.join(script_dir, "..")

search_paths = ["."]
home_path = os.environ.get('HOME')
if home_path is not None:
    search_paths.append(os.path.join(home_path, ".modbus_client/devices"))
search_paths.append(os.path.join(root_dir, "devices"))


def find_device_file(name: str) -> str:
    if not name.endswith(".yaml"):
        name = name + ".yaml"

    for sp in search_paths:
        full_path = os.path.join(sp, name)
        if os.path.exists(full_path):
            return full_path

    raise Exception("config file not found")
