#!/usr/bin/env python
__author__ = "Gao Wang"
__copyright__ = "Copyright 2016, Stephens lab"
__email__ = "gaow@uchicago.edu"
__license__ = "MIT"

# some loaded modules are used for exec()
import os, sys, re, glob
import warnings
warnings.filterwarnings("ignore")
from sos.utils import env, get_traceback
from .utils import uniq_list, flatten_list, workflow2html, dsc2html, Timer
from .addict import Dict as dotdict
from . import VERSION

class Silencer:
    def __init__(self, verbosity):
        self.verbosity = verbosity
        self.env_verbosity = env.verbosity

    def __enter__(self):
        env.verbosity = self.verbosity

    def __exit__(self, etype, value, traceback):
        env.verbosity = self.env_verbosity


def remove(workflows, groups, modules, db, debug, replace = False):
    import pickle
    from sos.__main__ import cmd_remove
    to_remove = [x for x in modules if os.path.isfile(x)]
    modules = [x for x in modules if x not in to_remove]
    modules = uniq_list(flatten_list([x if x not in groups else groups[x] for x in modules]))
    filename = '{}/{}.db'.format(db, os.path.basename(db))
    if not os.path.isfile(filename):
        env.logger.warning('Cannot remove ``{}``, due to missing output database ``{}``.'.\
                           format(repr(modules), filename))
    else:
        remove_modules = []
        for module in modules:
            removed = False
            for workflow in workflows:
                if module in workflow:
                    remove_modules.append(module)
                    removed = True
                    break
            if removed:
                remove_modules.append(module)
            else:
                env.logger.warning("Cannot remove target ``{}`` because it is neither files nor " \
                                   "modules defined in \"DSC::run\".".format(item))
        #
        data = pickle.load(open(filename, 'rb'))
        to_remove.extend(flatten_list([[glob.glob(os.path.join(db, '{}.*'.format(x)))
                                        for x in data[item]['FILE']]
                                       for item in remove_modules if item in data]))
    if len(to_remove):
        cmd_remove(dotdict({"tracked": False, "untracked": False,
                            "targets": uniq_list(to_remove), "external": True,
                            "__confirm__": True, "signature": False,
                            "verbosity": env.verbosity, "zap": True if replace else False,
                            "size": None, "age": None, "dryrun": debug}), [])
    else:
        env.logger.warning("No files found to {}. Please check your ``--target`` option".\
                           format('replace' if replace else 'purge'))

def execute(args):
    if args.to_remove:
        if args.target is None:
            raise ValueError("``--remove`` must be specified with ``--target``.")
        rm_objects = args.target
        args.target = None
    if args.target:
        env.logger.info("Load command line DSC sequence: ``{}``".\
                        format(' '.join(', '.join(args.target).split())))
    from .dsc_parser import DSC_Script, DSC_Pipeline
    from .dsc_translator import DSC_Translator
    from .dsc_database import ResultDB
    script = DSC_Script(args.dsc_file, output = args.output, sequence = args.target, extern = args.host)
    script.init_dsc(args, env)
    db = os.path.basename(script.runtime.output)
    pipeline_obj = DSC_Pipeline(script).pipelines
    if args.debug:
        workflow2html(f'.sos/.dsc/{db}.workflow.html', pipeline_obj, list(script.dump().values()))
    # FIXME: make sure try_catch works, or justify that it is not necessary to have.
    pipeline = DSC_Translator(pipeline_obj, script.runtime, args.replicates, args.__construct__ == "none",
                              args.__max_jobs__, args.try_catch)
    # Apply clean-up
    if args.to_remove:
        remove(pipeline_obj, {**script.runtime.concats, **script.runtime.groups},
               rm_objects, script.runtime.output,
               args.debug, args.to_remove == 'replace')
        return
    # Archive scripts
    lib_content = [(f"From <code>{k}</code>", sorted(glob.glob(f"{k}/*.*")))
                   for k in script.runtime.options['lib_path'] or []]
    exec_content = [(k, [script.modules[k].exe])
                    for k in script.runtime.sequence_ordering]
    dsc2html(open(args.dsc_file).read(), script.runtime.output,
             section_content = dict(lib_content + exec_content))
    env.logger.info(f"DSC script exported to ``{script.runtime.output}.html``")
    # Recover DSC from existing files
    if args.__construct__ == "all":
        if not ((os.path.isfile(f'{script.runtime.output}/{db}.map.mpk')
                 and os.path.isfile(f'{script.runtime.output}/{db}.io.mpk'))):
            raise RuntimeError('Project cannot be safely recovered because no meta-data can be found under\n``{}``'.\
                               format(os.path.abspath(script.runtime.output)))
        # FIXME: need test
        master = list(set([x[list(x.keys())[-1]].name for x in pipeline_obj]))
        ResultDB(f'{script.runtime.output}/{db}', master).Build(script = open(script.runtime.output + '.html').read(),
                                                                groups = script.runtime.groups)
        return
    # Setup
    env.logger.info(f"Constructing DSC from ``{args.dsc_file}`` ...")
    from sos.__main__ import cmd_run
    from sos.converter import script_to_html
    script_prepare = pipeline.write_pipeline(1)
    if args.debug:
        script_to_html(script_prepare, f'.sos/.dsc/{db}.prepare.html')
    mode = "default"
    if args.__construct__ == "none":
        mode = "force"
    import platform
    exec_path = [os.path.join(k, 'mac' if platform.system() == 'Darwin' else 'linux')
                 for k in (script.runtime.options['exec_path'] or [])] + (script.runtime.options['exec_path'] or [])
    exec_path = [x for x in exec_path if os.path.isdir(x)]
    # Get mapped IO database
    with Silencer(env.verbosity if args.debug else 0):
        content = {'__max_running_jobs__': args.__max_jobs__,
                   '__max_procs__': args.__max_jobs__,
                   '__sig_mode__': mode,
                   '__bin_dirs__': exec_path,
                   'script': script_prepare,
                   'workflow': "deploy"}
        cmd_run(script.get_sos_options(db + '.prepare', content), [])
    # Run
    env.logger.debug(f"Running command ``{' '.join(sys.argv)}``")
    env.logger.info("Building execution graph ...")
    pipeline.filter_execution()
    script_run = pipeline.write_pipeline(2)
    if args.debug:
        script_to_html(script_run, f'.sos/.dsc/{db}.run.html')
        return
    env.logger.info("DSC in progress ...")
    try:
        with Silencer(args.verbosity if args.host else min(1, args.verbosity)):
            content = {'__max_running_jobs__': args.__max_jobs__,
                       '__max_procs__': args.__max_jobs__,
                       '__sig_mode__': mode,
                       '__bin_dirs__': exec_path,
                       'script': script_run,
                       'workflow': "DSC"}
            cmd_run(script.get_sos_options(db + '.run', content), [])
    except Exception as e:
        if env.verbosity > 2:
            sys.stderr.write(get_traceback())
        sys.exit(1)
    # Build database
    master = list(set([x[list(x.keys())[-1]].name for x in pipeline_obj]))
    env.logger.info("Building DSC database ...")
    ResultDB('{}/{}'.format(script.runtime.output, db), master).\
        Build(script = open(script.runtime.output + '.html').read(), groups = script.runtime.groups)
    env.logger.info("DSC complete!")

def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, SUPPRESS
    class ArgumentParserError(Exception): pass
    class MyArgParser(ArgumentParser):
        def error(self, message):
            raise ArgumentParserError(message)
    #
    p = MyArgParser(description = __doc__, formatter_class = ArgumentDefaultsHelpFormatter)
    p.add_argument('--debug', action='store_true', help = SUPPRESS)
    p.add_argument('--version', action = 'version', version = '{}'.format(VERSION))
    p.add_argument('dsc_file', metavar = "DSC script", help = 'DSC script to execute.')
    p.add_argument('-o', metavar = "str", dest = 'output',
                   help = '''Benchmark output. It overwrites "DSC::run::output" defined in configuration file.''')
    p.add_argument('--target', metavar = "str", nargs = '+',
                   help = '''This argument can be used in two contexts:
                   1) When used without "--remove" it specifies "DSC::run" in DSC file.
                   Input should be quoted string(s) defining one or multiple valid DSC pipelines
                   (multiple pipelines should be separated by space).
                   2) When used along with "--remove" it specifies one or more computational modules,
                   separated by space, whose output are to be removed. Alternatively one can specify
                   path(s) of particular DSC output files that needs to be removed.''')
    p.add_argument('--replicates', metavar = "N", type = int, default = 1,
                   help = '''Number of replicates to be executed for every pipeline.''')
    p.add_argument('--skip', metavar = "option", choices = ["default", "none", "all"],
                   dest = '__construct__', default = "default",
                   help = '''Behavior of how DSC is executed in the presence of existing results.
                   "default": skips modules whose "environment" has not been changed since previous execution.
                   "none": executes DSC from scratch.
                   "all": skips all execution and attempts to build DSC database using existing results.
                   making it possible to explore partial benchmark results without having to complete the entire
                   benchmark.''')
    p.add_argument('--remove', metavar = "option", choices = ["purge", "replace"],
                   dest = 'to_remove',
                   help = '''Behavior of how DSC removes files specified by "--target".
                   "purge" deletes specified files
                   or files generated by specified modules. "replace" replaces these files by
                   dummy files with "*.zapped" extension, instead of removing them, so that
                   pipelines involving these files will continue to run until these files
                   are required by other modules. This is useful to swap out large intermediate files.''')
    p.add_argument('--host', metavar='str',
                   help='''Name of host computer to send tasks to.''')
    p.add_argument('-c', type = int, metavar = 'N', default = max(int(os.cpu_count() / 2), 1),
                   dest='__max_jobs__', help='''Number of maximum cpu threads.''')
    p.add_argument('--ignore-errors', action='store_true', dest='try_catch',
                   help = '''Bypass all errors from computational programs.
                   This will keep the benchmark running but
                   all results will be set to missing values and
                   the problematic script will be saved when possible.''')
    p.add_argument('-v', '--verbosity', type = int, choices = list(range(5)), default = 2,
                   help='''Output error (0), warning (1), info (2), debug (3) and trace (4)
                   information.''')
    p.set_defaults(func = execute)
    try:
        args = p.parse_args()
    except Exception as e:
        env.logger.error(e)
        env.logger.info("Please type ``{} -h`` to view available options".\
                        format(os.path.basename(sys.argv[0])))
        sys.exit(1)
    #
    env.verbosity = args.verbosity
    with Timer(verbose = True if (env.verbosity > 0) else False) as t:
        try:
            args.func(args)
        except Exception as e:
            if args.debug:
                raise
            if env.verbosity > 2:
                sys.stderr.write(get_traceback())
            env.logger.error(e)
            t.disable()
            sys.exit(1)

if __name__ == '__main__':
    main()
