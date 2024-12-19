import json
import argparse
from pathlib import Path
import shutil


def add_vendordep(vendordep_filename, is_beta):
    vendordep_contents = json.loads(vendordep_filename.read_bytes())
    year = vendordep_contents['frcYear'] + "beta" if is_beta else ""

    year_filename = Path(f"{year}.json")
    year_contents = json.loads(year_filename.read_bytes())
    
    metadata_filename = Path(f"{year}_metadata.json")
    metadata_contents = json.loads(metadata_filename.read_bytes())

    for metadata_lib in metadata_contents:
        if metadata_lib["uuid"] == vendordep_contents["uuid"]:
            break
    else:
        raise Exception("This appears to be a new library that does not have metadata associated with it. Can not automatically update")

    vendordep_destination = Path(f"{year}/{vendordep_filename.name}")
    
    year_contents.append(dict(
        path=str(vendordep_destination),
        name=metadata_lib["name"],
        version=vendordep_contents["version"],
        uuid=metadata_lib["uuid"],
        description=metadata_lib["description"],
        website=metadata_lib["website"],
    ))

    year_filename.write_text(json.dumps(year_contents, indent=2))
    shutil.copy(vendordep_filename, vendordep_destination)

def main():
    parser = argparse.ArgumentParser(
        "Generates one or more vendordep repository bundles for publication"
    )
    parser.add_argument(
        "--vendordep_file",
        type=Path
    )
    parser.add_argument(
        "--is_beta",
        type=bool
    )
    args = parser.parse_args()

    add_vendordep(args.vendordep_file, args.is_beta)




if __name__ == "__main__":
    main()