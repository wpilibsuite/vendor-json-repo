#!/usr/bin/env python3

import argparse
import configparser
import http
import io
import json
import os
import sys
import urllib.request
import uuid
import pathlib
from zipfile import ZipFile, BadZipFile

try:
    from elftools.elf.elffile import ELFFile
    from elftools.elf.constants import E_FLAGS, E_FLAGS_MASKS
    from elftools.elf.dynamic import DynamicSection
    from elftools.elf.sections import SymbolTableSection
except ImportError:
    print('elftools not found, run pip3 install pyelftools', file=sys.stderr)
    sys.exit(1)

try:
    import pefile
except ImportError:
    print('pefile not found, run pip3 install pefile', file=sys.stderr)
    sys.exit(1)

# Some webservers are set up to block urllib user agent, so override
urlopener = urllib.request.build_opener()
urlopener.addheaders = [('User-agent', 'Mozilla/5.0')]

#
# Message reporting
#

json_filename = ''
got_error = 0
got_warn = 0
message_context = []
cache_directory = None

def msg(t, s):
    ctx = ': '.join(message_context) + ': ' if message_context else ''
    print('{0}: {1}{2}{3}'.format(json_filename, t, ctx, s), file=sys.stderr)

def error(s):
    msg('ERROR: ', s)
    global got_error
    got_error += 1

def warn(s):
    msg('WARNING: ', s)
    global got_warn
    got_warn += 1

def info(s):
    msg('INFO: ', s)

#
# Global configuration
#

verbose = 0
local_maven = None
year = "2025"

def parse_args(argv):
    """Parse command line arguments.  Returns list of filenames."""
    parser = argparse.ArgumentParser(description='Checks a vendor json file')
    parser.add_argument('--verbose', '-v', action='count', help='increase the verbosity of output')
    parser.add_argument('--local-maven', help='directory to use for artifacts instead of fetching from mavenUrls')
    parser.add_argument('--year', '-y', help='FRC competition season year (used to set known libraries)')
    parser.add_argument('--cache_directory', type=pathlib.Path, help='Optional. If present will set up a download cache in this directory to prevent re-downloading artifacts. Should be used for debugging purposes only.')
    parser.add_argument('file', nargs='+', help='json file to parse')
    args = parser.parse_args(argv)

    global verbose, local_maven, year, cache_directory
    verbose = args.verbose or 0
    local_maven = args.local_maven
    year = args.year or "2025"
    cache_directory = args.cache_directory

    return args.file

#
# Per-file configuration
#

class FileConfig:
    def __init__(self):
        self.parser = None

    def load(self, json_fn):
        """Load configuration"""
        self.parser = configparser.ConfigParser(default_section='')
        basefn = os.path.splitext(json_fn)[0]
        self.parser.read([basefn + '.ini', basefn + '.cfg'])

    def getboolean(self, option):
        try:
            for section in reversed(message_context):
                rv = self.parser.getboolean(section, option, fallback=True)
                if rv is not None:
                    return rv
            return self.parser.getboolean('global', option, fallback=True)
        except ValueError as e:
            print('{0}: could not coerce {1} to boolean: {2}'.format(basefn + '.ini', option, e), file=sys.stderr)
            return True

file_config = FileConfig()

#
# JSON schema checker
#

def key_str(k):
    return '.'.join(k)

class Optional:
    def __init__(self, inner):
        self.inner = inner

json_schema = {
        'fileName': '',
        'name': '',
        'version': '',
        'frcYear': '',
        'uuid': '',
        'mavenUrls': [''],
        'jsonUrl': '',
        'requires': Optional([{
            'uuid': '',
            'errorMessage': '',
            'offlineFileName': '',
            'onlineUrl': '',
        }]),
        'conflictsWith': Optional([{
            'uuid': '',
            'errorMessage': '',
            'offlineFileName': '',
        }]),
        'javaDependencies': [{
            'groupId': '',
            'artifactId': '',
            'version': '',
            }],
        'jniDependencies': [{
            'groupId': '',
            'artifactId': '',
            'version': '',
            'isJar': False,
            'validPlatforms': [''],
            'skipInvalidPlatforms': False,
            'simMode': Optional(''),
            }],
        'cppDependencies': [{
            'groupId': '',
            'artifactId': '',
            'version': '',
            'libName': '',
            'configuration': Optional(''),
            'headerClassifier': '',
            'sourcesClassifier': Optional(''),
            'binaryPlatforms': Optional(['']),
            'skipInvalidPlatforms': Optional(False),
            'sharedLibrary': Optional(False),
            'simMode': Optional(''),
            }],
        }

def check_schema(j, schema, key):
    if isinstance(schema, Optional):
        schema = schema.inner
    if type(j).__name__ != type(schema).__name__:
        error('expected "{0}" to be {1}, but was {2}'.format(key_str(key), type(schema).__name__, type(j).__name__))
    if isinstance(j, dict):
        for k in j:
            if k not in schema:
                warn('unexpected key "{0}"'.format(key_str(key + (k,))))
                continue
            check_schema(j[k], schema[k], key + (k,))
        for k in schema:
            if k not in j and not isinstance(schema[k], Optional):
                error('missing key "{0}"'.format(key_str(key + (k,))))
    elif isinstance(j, list):
        for n, e in enumerate(j):
            check_schema(e, schema[0], key + (str(n),))
    elif isinstance(j, str):
        if not j:
            error('"{0}" cannot be empty string'.format(key_str(key)))

#
# Maven helpers
#

class MavenFetcher:
    def __init__(self, urls, group, artifact, version, ext):
        self.urls = [url + ('' if url.endswith('/') else '/') for url in urls]
        self.group = group
        self.artifact = artifact
        self.version = version
        self.ext = ext
        self.path = '/'.join(group.split('.')) + '/' + artifact + '/' + version + '/'

    def fetch(self, classifier, failok=False):
        fn = self.artifact + '-' + self.version
        if classifier is not None:
            fn += '-' + classifier
        fn += '.' + self.ext

        result = None

        if local_maven:
            path = os.path.join(local_maven, self.path, fn)
            if verbose >= 1:
                print('opening "{0}"'.format(path))
            try:
                with open(path, 'rb') as f:
                    result = f.read()
            except IOError as e:
                if not failok:
                    warn('could not open file: {1}'.format(path, e))
        else:
            for baseurl in self.urls:
                url = baseurl + self.path + fn
                maybe_cached_file = None
                if cache_directory:
                    maybe_cached_file = cache_directory / (self.path + fn)
                    if maybe_cached_file.exists():
                        if verbose >= 2:
                            print(f"Found a cache hit for {maybe_cached_file}")
                        return fn, maybe_cached_file.read_bytes()

                if verbose >= 1:
                    print('downloading "{0}"'.format(url))
                try:
                    with urlopener.open(url) as f:
                        result = f.read()
                    if maybe_cached_file:
                        maybe_cached_file.parent.mkdir(parents=True, exist_ok=True)
                        maybe_cached_file.write_bytes(result)
                except urllib.error.HTTPError as e:
                    if not failok:
                        warn('could not fetch url "{0}": {1}'.format(url, e))

        return fn, result

#
# Java artifact checks
#

def check_java_artifacts(dep, fetcher):
    #maven_check_pom_java(urls, group_id, artifact_id, version)

    fn, jar = fetcher.fetch(None)
    if jar is None:
        error('could not fetch java jar')

    fn, sources = fetcher.fetch('sources')
    if sources is None:
        warn('could not fetch java sources')

    fn, javadoc = fetcher.fetch('javadoc')
    if javadoc is None:
        warn('could not fetch java docs')

#
# C++ artifact checks
#

def check_cpp_sources(zf):
    cppfiles = [fn for fn in zf.namelist() if fn.endswith('.c') or fn.endswith('.cpp') or fn.endswith('.cc') or fn.endswith('.C')]
    if not cppfiles:
        warn('no C++ sources in sources zip')

def check_cpp_headers(zf):
    hfiles = [fn for fn in zf.namelist() if fn.endswith('.h') or fn.endswith('.hpp') or fn.endswith('.hh') or fn.endswith('.H')]
    if not hfiles:
        warn('no C++ headers in headers zip')

def check_cpp_shared_linux(libf, arch, debug):
    lib = ELFFile(libf)

    # check expected arch (for known arches)
    if arch == 'x86':
        if lib['e_machine'] != 'EM_386':
            error('arch mismatch, expected {0}, got {1}'.format('EM_386', lib['e_machine']))
    elif arch == 'x86-64':
        if lib['e_machine'] != 'EM_X86_64':
            error('arch mismatch, expected {0}, got {1}'.format('EM_X86_64', lib['e_machine']))
    elif arch == 'athena' or arch == 'raspbian':
        if lib['e_machine'] != 'EM_ARM':
            error('arch mismatch, expected {0}, got {1}'.format('EM_ARM', lib['e_machine']))
        else:
            if arch == 'athena' and (lib['e_flags'] & E_FLAGS.EF_ARM_ABI_FLOAT_SOFT) == 0:
                error('expected soft float')
            if arch == 'raspbian' and (lib['e_flags'] & E_FLAGS.EF_ARM_ABI_FLOAT_HARD) == 0:
                error('expected hard float')

    # check required libraries (excluding known libraries)
    exclude_libs = set([
        'libcscorejni.so',
        'libntcorejni.so',
        'libwpiHaljni.so',
        'libdl.so.2',
        'libatomic.so.1',
        'libstdc++.so.6',
        'libm.so.6',
        'libgcc_s.so.1',
        'libpthread.so.0',
        'libc.so.6',
        ])
    exclude_libs.update('lib{0}{1}.so'.format(l, 'd' if debug else '') for l in [
        'wpilibc',
        'cameraserver',
        'cscore',
        'ntcore',
        'wpiHal',
        'wpiutil',
        'wpimath',
        'wpinet',
        'wpilibNewCommands',
        ])
    if arch == 'athena':
        if year == "2025":
            exclude_libs.update([
                'libNiFpga.so.13',
                'libNiFpgaLv.so.13',
                'libniriodevenum.so.1',
                'libniriosession.so.1',
                'libNiRioSrv.so.13',
                'libRoboRIO_FRC_ChipObject.so.25',
                'libvisa.so',
                'libFRC_NetworkCommunication.so.25',
                ])
    dep_libs = []
    for section in lib.iter_sections():
        if not isinstance(section, DynamicSection):
            continue
        for tag in section.iter_tags():
            if tag.entry.d_tag == 'DT_NEEDED':
                if tag.needed in exclude_libs or tag.needed.startswith('libopencv_'):
                    continue
                dep_libs.append(tag.needed)

    if dep_libs:
        info('additional libs required: {0}'.format(dep_libs))

    # check to make sure no symbols are defined in frc:: namespace
    for section in lib.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue
        for symbol in section.iter_symbols():
            if symbol['st_info']['bind'] != 'STB_GLOBAL':
                continue
            if symbol['st_shndx'] == 'SHN_UNDEF':
                continue
            if symbol.name.startswith('_ZN3frc') or symbol.name.startswith('_ZNK3frc'):
                error('symbol defined in frc namespace: {0}'.format(symbol.name))

def check_cpp_shared_windows(libdata, arch, debug):
    lib = pefile.PE(data=libdata)

    # check required libraries (excluding known libraries)
    exclude_libs = set(l.lower() for l in [
        'cscorejni.dll',
        'ntcorejni.dll',
        'wpiHaljni.dll',
        'KERNEL32.dll',
        'api-ms-win-crt-runtime-l1-1-0.dll',
        'api-ms-win-crt-heap-l1-1-0.dll',
        'api-ms-win-crt-utility-l1-1-0.dll',
        'api-ms-win-crt-convert-l1-1-0.dll',
        'api-ms-win-crt-stdio-l1-1-0.dll',
        'api-ms-win-crt-filesystem-l1-1-0.dll',
        'api-ms-win-crt-locale-l1-1-0.dll',
        'api-ms-win-crt-math-l1-1-0.dll'
        'api-ms-win-crt-string-l1-1-0.dll',
        'api-ms-win-crt-environment-l1-1-0.dll', 
        'api-ms-win-crt-time-l1-1-0.dll'
        ])
    exclude_libs.update('{0}{1}.dll'.format(l, 'd' if debug else '').lower() for l in [
        'wpilibc',
        'cameraserver',
        'cscore',
        'ntcore',
        'wpiHal',
        'wpiutil',
        'wpimath',
        'wpinet',
        'wpilibNewCommands',
        'MSVCP140',
        'VCRUNTIME140',
        'VCRUNTIME140_1',
        'ucrtbase',
        ])
    dep_libs = []
    for entry in lib.DIRECTORY_ENTRY_IMPORT:
        dll = entry.dll.decode('utf-8')
        if dll.lower() in exclude_libs:
            continue
        dep_libs.append(dll)
    if dep_libs:
        info('additional libs required: {0}'.format(dep_libs))

def split_platform(platform):
    """convert platform into os+arch"""
    if platform.startswith('linux'):
        os = 'linux'
        arch = platform[5:]
    elif platform.startswith('windows'):
        os = 'windows'
        arch = platform[7:]
    elif platform.startswith('osx'):
        os = 'osx'
        arch = platform[3:]
    else:
        os = ''
        arch = ''

    return os, arch

def get_lib_prefix(os):
    if os == 'linux' or os == 'osx':
        return 'lib'
    else:
        return ''

def get_lib_ext(os, build):
    if build.startswith('static'):
        if os == 'linux' or os == 'osx':
            return '.a'
        elif os == 'windows':
            return '.lib'
    else:
        if os == 'linux':
            return '.so'
        elif os == 'windows':
            return '.dll'
        elif os == 'osx':
            return '.dylib'
    return ''

def get_full_libname(libName, os, build):
    """get platform-specific library and debug symbol filenames"""
    debugName = None
    if build.endswith('debug') and not file_config.getboolean('no_debug_suffix'):
        libName += 'd'
    if os == 'linux':
        if not build.startswith('static'):
            debugName = get_lib_prefix(os) + libName + get_lib_ext(os, build) + '.debug'

    return get_lib_prefix(os) + libName + get_lib_ext(os, build), debugName

def check_cpp_binary(zf, libName, platform, build):
    os, arch = split_platform(platform)
    if libName is None:
        # glob for it
        debugName = None
        ext = get_lib_ext(os, build)
        for fn in zf.namelist():
            if fn.endswith(ext):
                libName = fn.split('/')[-1]
    else:
        libName, debugName = get_full_libname(libName, os, build)

    # static/shared
    if build.startswith('static'):
        libType = 'static'
    else:
        libType = 'shared'

    # library must be in /os/arch/libType/
    expectpath = [os, arch, libType, libName]
    libpaths = [fn for fn in zf.namelist() if fn.split('/') == expectpath]
    if not libpaths:
        error('library {0} not found'.format('/'.join(expectpath)))
    elif libType == 'shared':
        lib = zf.read(libpaths[0])
        is_debug = build.endswith('debug')
        message_context.append(libName)
        if os == 'linux':
            check_cpp_shared_linux(io.BytesIO(lib), arch, is_debug)
        elif os == 'windows':
            check_cpp_shared_windows(lib, arch, is_debug)
        message_context.pop()

    if debugName is not None:
        expectpath = [os, arch, libType, debugName]
        dbgpaths = [fn for fn in zf.namelist() if fn.split('/') == expectpath]
        if not dbgpaths:
            info('debug symbols file {0} not found'.format('/'.join(expectpath)))

def check_cpp_artifacts(dep, fetcher):
    # sources
    if 'sourcesClassifier' in dep:
        fn, sources = fetcher.fetch(dep['sourcesClassifier'])
        if sources is None:
            warn('could not fetch sources')
        else:
            try:
                with ZipFile(io.BytesIO(sources)) as zf:
                    message_context.append(fn)
                    check_cpp_sources(zf)
                    message_context.pop()
            except BadZipFile:
                error('got bad sources zip')
    else:
        info('no sources')

    # headers
    if 'headerClassifier' in dep:
        fn, headers = fetcher.fetch(dep['headerClassifier'])
        if headers is None:
            error('could not fetch headers')
        else:
            try:
                with ZipFile(io.BytesIO(headers)) as zf:
                    message_context.append(fn)
                    check_cpp_headers(zf)
                    message_context.pop()
            except BadZipFile:
                error('got bad headers zip')
    else:
        info('no headers')

    # binaries
    for platform in dep.get('binaryPlatforms', []):
        for build in ['', 'debug', 'static', 'staticdebug']:
            # sharedLibrary specifies whether shared or static libraries are
            # used; we still check both if both exist but it's not an error
            # if the other kind is missing
            failok = (dep['sharedLibrary'] and build.startswith('static') or
                    not dep['sharedLibrary'] and not build.startswith('static'))
            fn, binary = fetcher.fetch(platform + build, failok=failok)
            if binary is None:
                if failok:
                    info('could not fetch optional binary platform {0} build {1}'.format(platform, build))
                elif platform == 'windowsx86':
                    warn('WPILib no longer builds for 32-bit')
                else:
                    error('could not fetch required C++ binary platform {0} build {1}'.format(platform, build))
            else:
                try:
                    with ZipFile(io.BytesIO(binary)) as zf:
                        message_context.append(fn)
                        check_cpp_binary(zf, dep['libName'], platform, build)
                        message_context.pop()
                except BadZipFile:
                    error('got bad binary zip')

def check_jni_artifacts(dep, fetcher):
    for platform in dep.get('validPlatforms', []):
        fn, binary = fetcher.fetch(platform)
        if binary is None:
            if platform == 'windowsx86':
                warn('WPILib no longer builds for 32-bit')
            else:
                error('could not fetch required JNI binary platform {0}'.format(platform))
        else:
            try:
                with ZipFile(io.BytesIO(binary)) as zf:
                    message_context.append(fn)
                    check_cpp_binary(zf, None, platform, '')
                    message_context.pop()
            except BadZipFile:
                error('got bad binary zip')

#
# Top level checks
#

def check_file(filename):
    if not os.path.exists(filename) :
        return

    with open(filename, 'rt') as f:
        j = json.load(f)

    # overall schema check
    check_schema(j, json_schema, ())
    if got_error:
        return

    # UUID should be a UUID
    try:
        u = uuid.UUID(j['uuid'])
    except ValueError:
        error('"uuid" is not a valid UUID')

    # need to have at least one maven location
    if not j['mavenUrls']:
        error('"mavenUrls" cannot be empty')

    if not j['javaDependencies']:
        warn('no Java dependencies (at least one is recommended)')

    if not j['cppDependencies']:
        warn('no C++ dependencies (at least one is recommended)')

    if not j['javaDependencies'] and not j['cppDependencies']:
        error('missing both Java and C++ dependencies')

    # should have linuxathena as at least one of the cppDependencies platforms
    if j['cppDependencies']:
        foundathena = False
        for dep in j['cppDependencies']:
            if 'linuxathena' in dep['binaryPlatforms']:
                foundathena = True
                break
        if not foundathena:
            warn('linuxathena binaryPlatform not found in any "cppDependencies"')

    # should have linuxathena as at least one of the jniDependencies platforms
    if j['jniDependencies']:
        foundathena = False
        for dep in j['jniDependencies']:
            if 'linuxathena' in dep['validPlatforms']:
                foundathena = True
                break
        if not foundathena:
            warn('linuxathena validPlatform not found in any "jniDependencies"')

    # Try to fetch the jsonUrl; we just want to make sure it's fetchable and a
    # JSON file, it won't necessarily match this file.
    if verbose >= 1:
        print('downloading "{0}"'.format(j['jsonUrl']))
    try:
        with urlopener.open(j['jsonUrl']) as f:
            j2 = json.load(f)
    except (urllib.error.HTTPError, http.client.IncompleteRead) as e:
        warn('could not fetch jsonUrl "{0}": {1}'.format(j['jsonUrl'], e))

    # Fetch artifacts from listed maven repos.  We have to be able to at least
    # fetch each artifact from one repo, but warn otherwise (as things may not
    # yet be mirrored, for example).
    for n, dep in enumerate(j['javaDependencies']):
        fetcher = MavenFetcher(j['mavenUrls'], dep['groupId'], dep['artifactId'], dep['version'], 'jar')
        message_context.append('javaDep.{0}'.format(n))
        check_java_artifacts(dep, fetcher)
        message_context.pop()

    for n, dep in enumerate(j['cppDependencies']):
        fetcher = MavenFetcher(j['mavenUrls'], dep['groupId'], dep['artifactId'], dep['version'], 'zip')
        message_context.append('cppDep.{0}'.format(n))
        check_cpp_artifacts(dep, fetcher)
        message_context.pop()

    for n, dep in enumerate(j['jniDependencies']):
        fetcher = MavenFetcher(j['mavenUrls'], dep['groupId'], dep['artifactId'], dep['version'], 'jar' if dep['isJar'] else 'zip')
        message_context.append('jniDep.{0}'.format(n))
        check_jni_artifacts(dep, fetcher)
        message_context.pop()

#
# Main
#

def main():
    had_errors = False
    for fn in parse_args(sys.argv[1:]):
        global json_filename, got_error, got_warn
        json_filename = fn
        got_error = 0
        got_warn = 0
        file_config.load(fn)
        check_file(fn)
        print('{0}: {1} errors, {2} warnings'.format(fn, got_error, got_warn), file=sys.stderr)
        if got_error > 0:
            had_errors = True
    sys.exit(1 if had_errors else 0)

if __name__ == '__main__':
    main()
