import sys
import json

if __name__ == "__main__":
    (_, year, version) = sys.argv
    print(f"Fixing up year {year} version {version}")

    with open(f"{year}.json", 'r') as f:
        current_year: list = json.load(f)
        current_year = [dep for dep in current_year if dep['version'] != version]
        print(current_year)
        current_year.append(
            {
                "path": f"{year}/photonlib-{version}.son",
                "name": "PhotonLib",
                "version": version,
                "uuid": "515fe07e-bfc6-11fa-b3de-0242ac130004",
                "description": "PhotonVision is the free, fast, and easy-to-use vision processing solution for the FIRST Robotics Competition.",
                "website": "https://docs.photonvision.org/en/latest/docs/programming/photonlib/adding-vendordep.html"
            }
        )
        print(current_year)
    with open(f"{year}.json", 'w') as f:
        json.dump(current_year, f, indent=4)