load("@rules_python//python:defs.bzl", "py_test")

def vendordep_check_test(vendor_file, allowable_warnings = 0, allowable_errors = 0, verbosity_level = "-v", cache_directory = None):
    file_no_extension = vendor_file[:-5]
    gen_name = file_no_extension + ".gen"
    test_file_base = file_no_extension + "_test"
    test_file_name = test_file_base + ".py"

    cache_replacement = ""
    if cache_directory:
        cache_replacement = 'args.append("--cache_directory=' + cache_directory + '")'

    verbosity_replacement = ""
    if verbosity_level:
        verbosity_replacement = 'args.append("' + verbosity_level + '")'

    test_contents = """

import unittest
from check import check_file, parse_args, file_config

class VendordepCheck(unittest.TestCase):
    def test_check(self):
        vendor_file = "{vendor_file}"
        warnings_allowed = {allowable_warnings}
        errors_allowed = {allowable_errors}

        args = [vendor_file]

        {verbosity_replacement}
        {cache_replacement}

        parse_args(args)
        file_config.load(vendor_file)
        check_file(vendor_file)

        from check import got_error, got_warn

        print(f"Errors: {{got_error}}")
        print(f"Warnings: {{got_warn}}")

        if errors_allowed is not None:
            self.assertLessEqual(got_error, errors_allowed)

        if warnings_allowed is not None:
            self.assertLessEqual(got_warn, warnings_allowed)


if __name__ == "__main__":
    unittest.main() # run all tests



""".format(
        vendor_file = vendor_file,
        allowable_warnings = allowable_warnings,
        allowable_errors = allowable_errors,
        cache_replacement = cache_replacement,
        verbosity_replacement = verbosity_replacement,
    )

    native.genrule(
        name = gen_name,
        outs = [test_file_name],
        cmd = "echo '{}' >> $@".format(test_contents),
    )
    py_test(
        name = test_file_base,
        srcs = [test_file_name],
        deps = ["//:check"],
        data = [vendor_file],
    )
