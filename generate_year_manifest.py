import argparse
import json
from pathlib import Path

def load_metadata(file: Path) -> dict[str, dict]:
    json_metadata = json.loads(file.read_text())
    out = {}
    for entry in json_metadata:
      out[entry["uuid"]] = entry
    return out


def generate_entry(file: Path, path_prefix: str, library_metadata: dict[str, dict]) -> dict[str, str]:
    vendordep_data = json.loads(file.read_text())
    if path_prefix and not path_prefix.endswith("/"):
        path_prefix += "/"
    uuid = vendordep_data["uuid"]
    return {
        "path": path_prefix + file.name,
        "name": library_metadata[uuid]["name"],
        "version": vendordep_data["version"],
        "uuid": uuid,
        "description": library_metadata[uuid]["description"],
        "website": library_metadata[uuid]["website"]
    }

def generate_manifest(json_dir: Path, metadata_file: Path, path_prefix: str, outfile: Path):
    """Generates a manifest for all vendordep json files in json_dir."""
    library_metadata = load_metadata(metadata_file)
    entries = []
    for file in json_dir.glob("*.json"):
        entries.append(generate_entry(file, path_prefix, library_metadata))
    outfile.write_text(json.dumps(entries, indent=2))


def main():
    parser = argparse.ArgumentParser("Generates a manifest from vendordep json files")
    parser.add_argument("--metadata", "-m", required=True, type=Path, help="the metadata file")
    parser.add_argument("--json-dir", "-j", required=True, type=Path, help="Directory that vendordep json files are in")
    parser.add_argument("--path-prefix", "-p", type=str, help="Optional. Path prefix to prepend to 'path' entries in the output. Defaults to the value of --json-dir.")
    parser.add_argument("outfile", type=Path)
    args = parser.parse_args()

    path_prefix = args.json_dir.as_posix()
    if args.path_prefix:
        path_prefix = args.path_prefix

    generate_manifest(args.json_dir, args.metadata, path_prefix, args.outfile)


if __name__ == "__main__":
    main()