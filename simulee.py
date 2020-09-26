from Evolution import *

def parse_function(target_file):
    global_env = Environment()
    Function.read_function_from_file_include_struct(target_file, global_env)
    return global_env

def check_drf(filename, used_default_dimension=False, fixed_dimension=None):
    for name, func in parse_function(filename).env.items():
        if isinstance(func, Function):
            auto_test_target_function(
                prog_file=ProgramFile(filename, name),
                used_default_dimension=used_default_dimension,
                fixed_dimension=fixed_dimension
            )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=str)
    parser.add_argument("--use-default-dimension", action="store_true", default=False)
    parser.add_argument("--fixed-dimensions", type=str, default=None)
    args = parser.parse_args()
    import json
    dims = json.loads(args.fixed_dimensions) if args.fixed_dimensions is not None else None
    check_drf(args.filename, args.use_default_dimension, dims)