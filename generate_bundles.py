import argparse
import json
import shutil
from pathlib import Path


def check_metadata_schema(metadata: list[dict]):
    required_keys = {"uuid", "name", "website", "description"}
    for entry in metadata:
        # no nested types, so just check root keys
        if not required_keys.issubset(entry.keys()):
            raise KeyError(
                f"Missing one or more required keys: {required_keys - entry.keys()}, metadata listing: {entry}"
            )


def load_metadata(file: Path) -> dict[str, dict]:
    json_metadata = json.loads(file.read_text())
    check_metadata_schema(json_metadata)
    out = {}
    for entry in json_metadata:
        out[entry["uuid"]] = entry
    return out


def generate_entry(
    file: Path, path_prefix: str, metadata_database: dict[str, dict]
) -> dict[str, str]:
    vendordep_data = json.loads(file.read_text())
    if path_prefix and not path_prefix.endswith("/"):
        path_prefix += "/"
    uuid = vendordep_data["uuid"]
    if uuid not in metadata_database.keys():
        raise KeyError(f"UUID for {file} not found in metadata.")
    metadata = metadata_database[uuid]
    # Metadata schemas have already been checked for required keys, so we can just add all the values to the output
    # This allows optional keys to be added as necessary without changing generation
    return metadata | {
        "path": path_prefix + file.name,
        "version": vendordep_data["version"],
    }


def generate_manifest_file(
    json_files: list[Path], metadata_file: Path, path_prefix: str, outfile: Path
):
    """Generates a manifest for all vendordep json files in json_files."""
    metadata_database = load_metadata(metadata_file)
    entries = []
    for file in json_files:
        entries.append(generate_entry(file, path_prefix, metadata_database))
    outfile.write_text(json.dumps(entries, indent=2), newline="\n")


def generate_bundle(year: str, root: Path, outdir: Path):
    """Generates a 'bundle' consisting of a YEAR.json manifest and a directory named YEAR containing all of the vendordep files

    Requires a metadata file YEAR_metadata.json, and a directory named YEAR containing the input vendordeps.
    """
    json_dir = root / year
    metadata = root / f"{year}_metadata.json"
    path_prefix = year
    outdir.mkdir(parents=True, exist_ok=True)

    manifest_file = Path(outdir) / f"{year}.json"
    vendordeps = [file for file in json_dir.glob("*.json")]

    generate_manifest_file(vendordeps, metadata, path_prefix, manifest_file)

    # Copy all vendordeps to outdir/YEAR
    depsdir = outdir / year
    depsdir.mkdir(exist_ok=True)
    for file in vendordeps:
        shutil.copy(file, depsdir)


def main():
    parser = argparse.ArgumentParser(
        "Generates one or more vendordep repository bundles for publication"
    )
    parser.add_argument(
        "--output", "-o", type=Path, default="bundles", help="Directory to place the output bundles in"
    )
    parser.add_argument(
        "--root",
        "-r",
        type=Path,
        default=Path(),
        help="Root directory to find metadata files and year folders. Defaults to '.'",
    )
    parser.add_argument(
        "year", nargs="+", type=str, help="Years to generate bundles for"
    )
    args = parser.parse_args()

    for year in args.year:
        generate_bundle(year, args.root, args.output)


if __name__ == "__main__":
    main()
