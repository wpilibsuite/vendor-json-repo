# WPILib Vendor JSON Repository

The GradleRIO build system supports the addition of vendor libraries through JSON files added to the vendordeps/ directory of the project.  While vendor artifacts are published via Maven, the Maven ecosystem alone is insufficient for straightforward handling of multi-platform JNI and C++ libraries.  Each vendor JSON file is a standalone complete description of all Maven dependencies and related configuration required to include the vendor library in either a C++ or Java GradleRIO robot project.

This repository serves as a central repository for vendor libraries that are likely to be used by a large number of FRC teams.  Additions to this repository, in particular its master directory, are accepted on a case-by-case basis with guidance from FIRST.

## Repository structure

Each year (e.g. competition season) has a JSON file at the root level (named `YEAR.json`) and a directory (named `YEAR/`) of vendor JSON files.

### YEAR.json

The root-level `YEAR.json` files (e.g. `2024.json`) provide the master directory of available vendor libraries.  It's intended to be used by IDEs such as Visual Studio Code to present a user-friendly list of available vendor libraries.

This json file consists of a list of dicts with the following keys:
* path: the path within the repository to the vendor JSON file (e.g. `2024/<vendor>-<version>.json`)
* name: the same as the name in the vendor JSON file (`<vendor>-<version>.json`)
* uuid: the same as the uuid in the vendor JSON file
* description: a user-friendly brief description of the library -- intended to be displayed to users in list format
* website: URL of the vendor's website (e.g. a site with documentation / tutorials / tools installers)

## JSON checker

To assist in making sure that vendor JSON files and their associated Maven dependencies are correct, a checker script (check.py) is provided.  This Python 3 script is run automatically on each PR, and can also be run manually on any checkout.  While the checks performed do not include actually trying to build a robot program, they are designed to ensure that the JSON file and Maven dependencies will work within the build ecosystem.

Usage: `check.py [-v] [--local-maven LOCAL_MAVEN] [--year YEAR] file [file ...]`

The primary output of check.py consists of ERROR, WARNING, and INFO messages.  ERROR messages must be fixed in order for the JSON file to work within the build ecosystem.  WARNINGs are cautionary: something isn't right, but builds will likely work.  INFO messages are informational.

Normally, check.py downloads Maven artifacts from the mavenUrls specified in the JSON file.  However, to enable testing of artifacts before they are published, the `--local-maven` option can be used to instead pull the artifacts from a local Maven repository; the parameter to this option specifies the directory path of the root of the Maven repo.

The checker also supports per-file configuration via the use of .ini files; the .ini file must be located in the same directory and named the same as the JSON file (just with a .ini instead of .json extension).  The `[global]` section specifies options that are applied globally; options can be applied more precisely by using a section name corresponding to the message context; for example a message such as `INFO: cppDep.0: ...` has a context of `cppDep.0` and options can be applied to that context by putting them in the `[cppDep.0]` ini section.

Currently only one option is supported: `no_debug_suffix`.  Normally debug libraries have a `d` suffix appended to disambiguate them from the non-debug libraries (e.g. `libvendor.so` and `libvendord.so`).  Setting this option to true disables appending of the `d` suffix.

The check.py script requires the `pyelftools` and `pefile` dependencies be installed; use `pip3 install` to install these.

## Bazel Testing
Pyunit tests are automatically auto generated run using the checker tool against all of the vendordep json files in the repository by bazel.

### Prerequisites
- Install [Bazelisk](https://github.com/bazelbuild/bazelisk/releases) and add it to your path. Bazelisk is a wrapper that will download the correct version of bazel specified in the repository. Note: You can alias/rename the binary to `bazel` if you want to keep the familiar `bazel build` vs `bazelisk build` syntax.

### Running the tests
To run the tests, simply run `bazel test //...`. Alternatively, you can run the `checker.py` tool in a standalone mode by running `bazel run //:checker -- <command line arguments from above>`
