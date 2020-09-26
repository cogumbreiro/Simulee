from Evolution import *
import sys

def parse_function(target_file, filter_unknown=True):
    global_env = Environment()
    Function.read_function_from_file_include_struct(target_file, global_env, filter_unknown)
    return global_env

algorithm_func = {
    "dr": auto_test_target_function,
    "dr+bd": auto_test_target_function_dynamical,
    "dr+bd+rb": auto_test_target_function_advanced
}

def check_drf(filename, fixed_tid=False, initial_tid=None, algorithm="default", kernel_name=None, filter_unknown=True):
    kernel_names = []
    if kernel_name is not None:
        kernel_names = [kernel_name]
        filter_unknown = False
    else:
        kernel_names = list(
            name
            for name, func in parse_function(filename, filter_unknown).env.items()
            if isinstance(func, Function)
        )

    if len(kernel_names) == 0 and filter_unknown:
        kernel_names = ", ".join(parse_function(filename, filter_unknown=False).env.keys())
        print >> sys.stderr, "Could not find any kernel. Use --kernel-name instead or pass --include-all-functions.\nAvailable kernel names:", kernel_names
        sys.exit(1)
        return

    for name in kernel_names:
        algorithm_func[algorithm](
            prog_file=ProgramFile(filename, name, filter_unknown),
            used_default_dimension=fixed_tid,
            fixed_dimension=initial_tid,
        )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=str)
    parser.add_argument("--kernel-name", default=None, help="Force verification of a single kernel.")
    parser.add_argument("--include-all-functions", dest="filter_unknown", default=True, action="store_false", help="Some files do not mark the kernels in the LLVM IR, use this flag to check all kernels instead.")
    parser.add_argument("--fixed-tid", action="store_false", default=False, help="Use fixed TIDs. Do not range over TID with the evolution algorithm.")
    parser.add_argument("--initial-tid", dest="fixed_dimensions", type=str, default=None, help="Set initial TID. Default=[[1, 1, 1], [34, 1, 1]]")
    parser.add_argument("--algorithm", type=str, default="dr", choices=list(algorithm_func.keys()))
    args = parser.parse_args()
    import json
    dims = json.loads(args.initial_tid) if args.fixed_dimensions is not None else None
    check_drf(
        filename=args.filename,
        fixed_tid=args.fixed_tid,
        initial_tid=dims,
        algorithm=args.algorithm,
        kernel_name=args.kernel_name,
        filter_unknown=args.filter_unknown
    )