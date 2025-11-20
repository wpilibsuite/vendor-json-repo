# WPILib Vendor JSON Repository

The GradleRIO build system supports the addition of vendor libraries through JSON files added to the vendordeps/ directory of the project.  While vendor artifacts are published via Maven, the Maven ecosystem alone is insufficient for straightforward handling of multi-platform JNI and C++ libraries.  Each vendor JSON file is a standalone complete description of all Maven dependencies and related configuration required to include the vendor library in either a C++ or Java GradleRIO robot project.

This repository serves as a central repository for vendor libraries that are likely to be used by a large number of FRC teams.  Additions to this repository are accepted on a case-by-case basis with guidance from FIRST.

The automation in this repository (in particular, [.github/workflows/generate_bundles.yml](.github/workflows/generate_bundles.yml)) generates a repository format suitable for consumption by the WPILib VSCode plugin (See #bundle-repository-structure). This is published to a [repository on the WPILib Artifactory server](https://frcmaven.wpi.edu/ui/native/vendordeps/vendordep-marketplace/).

## Quick Start

To add a new library, add a metadata entry to the metadata file for a given bundle (`YEAR_metadata.json`, see [here](#bundle-metadata-file) for the required/permitted keys), and add a vendordep JSON file for the library to the `YEAR` directory.

To add a new version of an existing library, simply add the vendordep JSON file for the new version into the `YEAR` directory.

In both cases, the vendordep JSON file should be named `NAME-VERSION.json` (see [Repository Structure](#repository-structure)).

## Repository structure

This git repository contains sources to generate one or more "bundles" of vendordeps. A bundle is a set of vendordep JSON files and an associated manifest that are designed to be consumed by a specific release series (such as a competition season or alpha/beta period) of tooling such as IDEs. For the generated bundle format, see [here](#bundle-repository-structure).

Each bundle is generated from a directory in the root of this repository (named `YEAR/`) containing vendordep JSON files, and a metadata file (also in the root of this repository, named `YEAR_metadata.json`) that provides metadata needed to generate the bundle manifest.

For bundles targeting a season release series, `YEAR` above shall be replaced with the competition season (e.g. `2024`). For bundles targeting a prerelease series, `YEAR` shall be replaced with `YEARalpha` or `YEARbeta`, where `YEAR` is the competition season the prerelease series is for (e.g. `2025beta`). (Note: this convention matches the WPILib VSCode plugin preferences `projectYear` entry)

Vendordep JSON files associated with a bundle are placed inside the bundle's directory. They should be named `NAME-VERSION.json`, where `NAME` is the unique name of the library and `VERSION` is the version of the library that the vendordep JSON represents.

### Bundle metadata file

Each bundle metadata file (`YEAR_metadata.json`) shall contain a list of library metadata entries as dicts. Each library shall be represented by a single metadata entry in a given bundle's metadata file.

Each entry shall contain, at minimum, the following keys:

* `name`: A user-friendly name for the library
* `uuid`: The uuid for the library (present inside each of the library's vendordep JSON files)
* `description`: a user-friendly brief description of the library (intended to be displayed to users)
* `website`: URL of the vendor's website (e.g. a site with documentation / tutorials / tools installers) (note: currently unused by the WPILib VSCode plugin)

Additionally, the entry may contain any of the following optional keys:

* `instructions`: URL of an "instructions" page that can be shown after the user installs this library.

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

## Bundle repository structure

Each published bundle of vendordeps (typically, a competition season or alpha/beta period) has a JSON file (named `YEAR.json`) at the root level of the published repository and a directory (named `YEAR/`) of vendor JSON files.

### Bundle manifest (YEAR.json)

The root-level `YEAR.json` files (e.g. `2025.json`) provide a manifest of all available libraries and versions for a given bundle. It's intended to be used by IDEs such as Visual Studio Code to present a user-friendly list of available vendor libraries.

This manifest is a JSON file and consists at minimum of a list of dicts (one corresponding to each individual vendordep JSON file in the bundle) with the following keys:
* `path`: the path relative to the manifest to the vendordep JSON file (e.g. `2025/<vendordep>-<version>.json`)
* `name`: A user-friendly name for the library
* `version`: The version of the library
* `uuid`: the same as the uuid in the vendor JSON file
* `description`: a user-friendly brief description of the library (intended to be displayed to users)
* `website`: URL of the vendor's website (e.g. a site with documentation / tutorials / tools installers)
* `languages`: an array of strings indicating the languages supported by the library. Currently used values are "cpp" and "java".

Additionally, the following optional keys may be present in a manifest entry:

* `instructions`: URL of an "instructions" page that can be shown after the user installs this library.

## Maintenance documentation

### Creating new bundles

To create a new bundle and add it to the CI job to be checked, generated, and published:

* Create a directory (`YEAR/`) and metadata file (`YEAR_metadata.json`) for the bundle. They can be empty for now.
* In `.github/workflows/generate_bundles.yml`, add the new bundle name to the arguments for `generate_bundles.py`
* In `.github/workflows/main.yml`, change the `YEAR` environment variable to the name of the new bundle (note: only one bundle is checked by this workflow currently)
* Add a new test configuration to `BUILD.bazel`

## Automatically creating pull requests
If your libraries CI creates a new vendordep.json file, you can use an action contained in this repository to automatically create a pull request to add your changes. In order for the action to work, you must define a secret with write access to be able to create the pull request.

Here is an example workflow:

```yml
jobs:
  hello_world_job:
    runs-on: ubuntu-latest
    name: A job to say hello
    steps:
      - uses: actions/checkout@v4

      # Steps to package your vendordep file. It is recommended that you store the new version number in a variable so that it can be used later when creating your PR's title and branch name

      - name: Create Vendor JSON Repo PR
        uses: wpilibsuite/vendor-json-repo/.github/actions/add_vendordep@latest
        with:
          repo: <GH account>/<vendor-json-repo fork name>
          token: ${{ secrets.PUBLISH_VENDOR_JSON_TOKEN }}
          vendordep_file: <path to vendordep file>
          pr_title: "Automatically add <library name> version <version>"
          pr_branch: "publish_<library name>_<version>"
```