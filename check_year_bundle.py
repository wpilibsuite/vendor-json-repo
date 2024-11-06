#!/usr/bin/env python3

import os
import sys
import argparse
import pathlib
import json
from dataclasses import dataclass
import uuid


@dataclass
class Results:
    uuid_errors: int = 0
    bad_file_errors: int = 0
    duplicate_version_errors: int = 0
    inconsistent_version_errors: int = 0
    missing_description_errors: int = 0
    missing_website_errors: int = 0
    uncovered_file_errors: int = 0

    def is_valid(self):
        valid = True

        valid = valid and self.uuid_errors == 0
        valid = valid and self.bad_file_errors == 0
        valid = valid and self.duplicate_version_errors == 0
        valid = valid and self.inconsistent_version_errors == 0
        valid = valid and self.missing_description_errors == 0
        valid = valid and self.missing_website_errors == 0
        valid = valid and self.uncovered_file_errors == 0

        return valid


def check_year_bundle(year: int) -> Results:
    bundled_json_file = pathlib.Path(f"{year}.json")
    json_data = json.loads(bundled_json_file.read_text())

    vendordep_versions = {} # Name -> set[version]
    vendordep_uuid = {} # Name -> UUID
    
    results = Results()
    covered_files = set()

    for dep in json_data:
        if dep["name"] not in vendordep_versions:
            vendordep_versions[dep["name"]] = set()

        resolved_path = dep["path"]
        file_json_data = None

        # Check file existence
        if not os.path.exists(resolved_path):
            print(f"{dep['path']} - Could not find file")
            results.bad_file_errors += 1
        else:
            file_json_data = json.load(open(resolved_path))
            covered_files.add(resolved_path)
        
        # Check description
        if "description" not in dep:
            print(f"{dep['path']} - Missing description")
            results.missing_description_errors += 1

        # Check website
        if "website" not in dep:
            print(f"{dep['path']} - Missing documentation website")
            results.missing_website_errors += 1

        # Check version
        if dep["version"] in vendordep_versions[dep["name"]]:
            print(f"{dep['path']} - Duplicated version {dep['version']}")
            results.duplicate_version_errors += 1
        vendordep_versions[dep["name"]].add(dep["version"])

        if file_json_data is not None and file_json_data["version"] != dep["version"]:
            print(f"{dep['path']} - Version {dep['version']} does not match the version in the file {file_json_data['version']}")
            results.inconsistent_version_errors +=1 

        # Check UUID
        if dep["name"] not in vendordep_uuid:
            vendordep_uuid[dep["name"]] = dep["uuid"]
        
        if vendordep_uuid[dep["name"]] != dep["uuid"]:
            print(f"{dep['path']} - UUID {dep['uuid']} has has changed from previously seen UUID {vendordep_uuid[dep['name']]}")
            results.uuid_errors += 1

        if file_json_data is not None and file_json_data["uuid"] != dep["uuid"]:
            print(f"{dep['path']} - UUID {dep['uuid']} does not match the UUID in the file {file_json_data['uuid']}")
            results.uuid_errors += 1

        try:
            uuid.UUID(dep["uuid"])
        except:
            print(f"{dep['path']} - UUID {dep['uuid']} is invalid")
            results.uuid_errors += 1

    # Look for uncovered files            
    all_files = set([os.path.join(str(year), x) for x in os.listdir(str(year))])
    uncovered_files = all_files.difference(covered_files)
    for f in uncovered_files:
        print(f"File {f} is not represented in the year bundle")
        results.uncovered_file_errors += 1

    # Check that UUID's are unique across vendordeps
    if len(vendordep_uuid) != len(set(vendordep_uuid.values())):
        print(f"There are a different number of vendordeps ({len(vendordep_uuid)}) than there are UUIDs ({len(set(vendordep_uuid.values()))}), indicating UUID's have been reused between vendordeps")
        results.uuid_errors += 1

    # Print known versions
    print("Known versions:")
    for k in vendordep_versions:
        print(f"  {k} - {vendordep_versions[k]}")

    return results



def main():
    parser = argparse.ArgumentParser(description='Checks a vendor json file')
    parser.add_argument('--year', '-y', required=True, help='FRC competition season year')
    args = parser.parse_args(sys.argv[1:])

    results = check_year_bundle(args.year)

    print(results)
    sys.exit(results.is_valid(args.disable_uuid_check))



if __name__ == "__main__":
    main()

