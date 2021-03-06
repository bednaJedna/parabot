from io import StringIO
from multiprocessing import Process, get_context
from multiprocessing.context import TimeoutError  # pylint: disable=redefined-builtin
from typing import Any, Callable, List, Optional, Union

from robot.run import run  # type: ignore

from parabot.utils import (
    create_output_folder,
    get_all_robot_files,
    get_parent_dir,
    get_specific_robot_files_by_paths,
    parse_args,
)


def _check_stderr(stderr: Any) -> Optional[int]:
    # pylint: disable=no-else-return
    if stderr.getvalue() != "":
        print(stderr.getvalue())
        stderr.close()
        return 1
    else:
        stderr.close()
        return None


def path_worker(filepath: Any) -> Optional[int]:
    """Worker used by Pool.

    Runs instance of RobotFramework for given .robot file.
    
    Arguments:
        filepath {Any} -- python PurePath to .robot file to be executed by robot.run.run

    Returns:
        status {Optional[int]} -- None:OK, 1: NOK
    
    See:
        https://docs.python.org/3/library/pathlib.html
        https://robot-framework.readthedocs.io/en/v3.1.2/autodoc/robot.html#module-robot.run
    """
    basepath: Any = get_parent_dir(filepath)
    stdout: Any = StringIO()
    stderr: Any = StringIO("")
    run(
        filepath,
        outputdir=create_output_folder(basepath, filepath.name),
        stdout=stdout,
        stderr=stderr,
    )
    print(stdout.getvalue())
    stdout.close()

    return _check_stderr(stderr)


def tag_worker(tag: str) -> Optional[int]:
    """Worker used by Process.

    Runs instance of RobotFramework for given tag.
    
    Arguments:
        tag {str} -- tag

    Returns:
        status {Optional[int]} -- None: OK, 1: NOK
    
    See:
        https://robot-framework.readthedocs.io/en/v3.1.2/autodoc/robot.html#module-robot.run
    """
    stdout: Any = StringIO()
    stderr: Any = StringIO("")
    run(
        "./",
        outputdir=create_output_folder("./reports/", tag),
        include=[tag],
        stdout=stdout,
        stderr=stderr,
    )
    print(stdout.getvalue())
    stdout.close()

    return _check_stderr(stderr)


def pool_path_workers(
    path_worker: Callable, filepathslist: List[Any], timeout=60
) -> Union[List[Optional[int]], int]:
    """Runs path_worker against list of arguments in parallel.

    Max. number of parallel processes is limited by no. of CPUs cores.
    
    Arguments:
        path_worker {Callable} -- path_worker function
        filepathslist {List[Any]} -- list of python PurePaths to .robot files
        timeout {int} -- timeout for async pool.map_async method. Can be altered by passing
        [-to <int>] or [--timeout <int>] CLI argument 
    
    Returns:
        status {Union[List[Optional[int]], int]} -- None:OK, 1:NOK
    """
    with get_context("spawn").Pool(maxtasksperchild=1) as p:
        try:
            return p.map_async(path_worker, filepathslist).get(timeout)
        except TimeoutError:
            print(
                "Your tests are running too long. Consider increasing the timeout via CLI parameter -to or --timeout."
            )
            return 1


def pool_tag_workers(tag_worker: Callable, tags: List[str]) -> List[Optional[int]]:
    """Runs tag_worker against list of tags in parallel.

    For each tag is spawned one process.
    
    Arguments:
        tag_worker {Callable} -- tag_worker function
        tags {List[str]} -- list of tags

    Returns:
        {List[Optional[int]]} -- None: if process not yet terminated,
        0: if process terminated, -N if process terminated by signal N

    See:
        https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.exitcode 
    """
    procesess: List[Any] = []

    for tag in tags:
        p: Any = Process(target=tag_worker, args=(tag,))
        p.start()
        procesess.append(p)

    # pylint: disable=expression-not-assigned
    [proc.join() for proc in procesess]

    return [proc.exitcode for proc in procesess]


def main() -> None:
    """Main function.

    See:
        https://stackoverflow.com/questions/30487767/check-if-argparse-optional-argument-is-set-or-not
    """
    filepathslist: List[Any]
    args: Any = parse_args()

    if args.all and (args.timeout is None):
        filepathslist = get_all_robot_files()
        pool_path_workers(path_worker, filepathslist)
    elif args.all and (args.timeout is not None):
        filepathslist = get_all_robot_files()
        pool_path_workers(path_worker, filepathslist, timeout=args.timeout)

    if (args.folders is not None) and (args.timeout is None):
        filepathslist = get_specific_robot_files_by_paths(args.folders)
        pool_path_workers(path_worker, filepathslist)
    elif (args.folders is not None) and (args.timeout is not None):
        filepathslist = get_specific_robot_files_by_paths(args.folders)
        pool_path_workers(path_worker, filepathslist, timeout=args.timeout)

    if args.tags is not None:
        pool_tag_workers(tag_worker, args.tags)


if __name__ == "__main__":
    main()
