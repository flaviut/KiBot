# -*- coding: utf-8 -*-
# Copyright (c) 2020-2023 Salvador E. Tropea
# Copyright (c) 2020-2023 Instituto Nacional de Tecnología Industrial
# Copyright (c) 2018 John Beard
# License: GPL-3.0
# Project: KiBot (formerly KiPlot)
# Adapted from: https://github.com/johnbeard/kiplot
"""KiBot: KiCad automation tool for documents generation

Usage:
  kibot [-b BOARD] [-e SCHEMA] [-c CONFIG] [-d OUT_DIR] [-s PRE] [-D]
         [-q | -v...] [-L LOGFILE] [-C | -i | -n] [-m MKFILE] [-A] [-g DEF] ...
         [-E DEF] ... [-w LIST] [--banner N] [TARGET...]
  kibot [-v...] [-b BOARD] [-e SCHEMA] [-c PLOT_CONFIG] [--banner N]
         [-E DEF] ... [--config-outs] [--only-pre|--only-groups] [--only-names]
         [--output-name-first] --list
  kibot [-v...] [-c PLOT_CONFIG] [--banner N] [-E DEF] ... [--only-names]
         --list-variants
  kibot [-v...] [-b BOARD] [-d OUT_DIR] [-p | -P] [--banner N] --example
  kibot [-v...] [--start PATH] [-d OUT_DIR] [--dry] [--banner N]
         [-t, --type TYPE]... --quick-start
  kibot [-v...] [--rst] --help-filters
  kibot [-v...] [--markdown|--json|--rst] --help-dependencies
  kibot [-v...] [--rst] --help-global-options
  kibot [-v...] [--rst] --help-list-outputs
  kibot [-v...] --help-output=HELP_OUTPUT
  kibot [-v...] [--rst] [-d OUT_DIR] --help-outputs
  kibot [-v...] [--rst] --help-preflights
  kibot [-v...] [--rst] --help-variants
  kibot [-v...] --help-banners
  kibot [-v...] [--rst] --help-errors
  kibot -h | --help
  kibot --version

Arguments:
  TARGET    Outputs to generate, default is all

Options:
  -A, --no-auto-download           Disable dependencies auto-download
  -b BOARD, --board-file BOARD     The PCB .kicad-pcb board file
  --banner N                       Display banner number N (-1 == random)
  -c CONFIG, --plot-config CONFIG  The plotting config file to use
  -C, --cli-order                  Generate outputs using the indicated order
  --config-outs                    Configure all outputs before listing them
  -d OUT_DIR, --out-dir OUT_DIR    The output directory [default: .]
  -D, --dont-stop                  Try to continue if an output fails
  -e SCHEMA, --schematic SCHEMA    The schematic file (.sch/.kicad_sch)
  -E DEF, --define DEF             Define preprocessor value (VAR=VAL)
  -g DEF, --global-redef DEF       Overwrite a global value (VAR=VAL)
  -i, --invert-sel                 Generate the outputs not listed as targets
  -l, --list                       List available outputs, preflights and
                                   groups (in the config file).
                                   You don't need to specify an SCH/PCB unless
                                   using --config-outs
  --list-variants                  List the available variants and exit
  -L, --log LOGFILE                Log to LOGFILE using maximum debug level.
                                   Is independent of what is logged to stderr
  -m MKFILE, --makefile MKFILE     Generate a Makefile (no targets created)
  -n, --no-priority                Don't sort targets by priority
  -p, --copy-options               Copy plot options from the PCB file
  --only-names                     Print only the names. Note that for --list
                                   if no other --only-* option is provided it
                                   also acts as a virtual --only-outputs
  --only-groups                    Print only the groups.
  --only-pre                       Print only the preflights
  --output-name-first              Use the output name first when listing
  -P, --copy-and-expand            As -p but expand the list of layers
  -q, --quiet                      Remove information logs
  -s PRE, --skip-pre PRE           Skip preflights, comma separated or `all`
  -v, --verbose                    Show debugging information
  -V, --version                    Show program's version number and exit
  -w, --no-warn LIST               Exclude the mentioned warnings (comma sep)
  -x, --example                    Create a template configuration file

Quick start options:
  --quick-start                    Generates demo config files and their outputs
  --dry                            Just generate the config files
  --start PATH                     Starting point for the search [default: .]
  -t, --type TYPE                  Generate examples only for the indicated type/s

Help options:
  -h, --help                       Show this help message and exit
  --help-banners                   Show all available banners
  --help-dependencies              List dependencies in human readable format
  --help-errors                    List of error levels
  --help-filters                   List supported filters and details
  --help-global-options            List supported global variables
  --help-list-outputs              List supported outputs
  --help-output HELP_OUTPUT        Help for this particular output
  --help-outputs                   List supported outputs and details
  --help-preflights                List supported preflights and details
  --help-variants                  List supported variants and details

"""
from datetime import datetime
from glob import glob
import gzip
import locale
import os
import platform
import re
import sys
from sys import path as sys_path
from . import __version__, __copyright__, __license__
# Import log first to set the domain
from . import log
log.set_domain('kibot')
logger = log.init()
from .docopt import docopt
# GS will import pcbnew, so we must solve the nightly setup first
# Check if we have to run the nightly KiCad build
nightly = False
if os.environ.get('KIAUS_USE_NIGHTLY'):  # pragma: no cover (nightly)
    # Path to the Python module
    pcbnew_path = '/usr/lib/kicad-nightly/lib/python3/dist-packages'
    sys_path.insert(0, pcbnew_path)
    # This helps other tools like iBoM to pick-up the right pcbnew module
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] += os.pathsep+pcbnew_path
    else:
        os.environ['PYTHONPATH'] = pcbnew_path
    nightly = True
from .banner import get_banner, BANNERS
from .gs import GS
from . import dep_downloader
from .misc import EXIT_BAD_ARGS, W_VARCFG, NO_PCBNEW_MODULE, W_NOKIVER, hide_stderr, TRY_INSTALL_CHECK, W_ONWIN
from .pre_base import BasePreFlight
from .error import KiPlotConfigurationError, config_error
from .config_reader import (CfgYamlReader, print_outputs_help, print_output_help, print_preflights_help, create_example,
                            print_filters_help, print_global_options_help, print_dependencies, print_variants_help,
                            print_errors)
from .kiplot import (generate_outputs, load_actions, config_output, generate_makefile, generate_examples, solve_schematic,
                     solve_board_file, solve_project_file, check_board_file)
from .registrable import RegOutput
GS.kibot_version = __version__


def list_pre_and_outs_names(logger, outputs, do_config, only_pre, only_groups):
    pf = BasePreFlight.get_in_use_names()
    if only_pre:
        for c in sorted(pf):
            logger.info(c)
        return
    if only_groups:
        for g in sorted(RegOutput.get_group_names()):
            logger.info(g)
        return
    if outputs:
        for o in sorted(outputs, key=lambda x: x.name.lower()):
            if do_config:
                config_output(o, dry=False)
            logger.info(o.name)


def list_pre_and_outs(logger, outputs, do_config, only_names, only_pre, only_groups, output_name_first):
    if only_names:
        return list_pre_and_outs_names(logger, outputs, do_config, only_pre, only_groups)
    pf = BasePreFlight.get_in_use_objs()
    groups = RegOutput.get_groups()
    if pf and not only_groups:
        logger.info('Available pre-flights:')
        for c in pf:
            logger.info('- '+str(c))
        logger.info("")
    if outputs and not only_pre and not only_groups:
        fmt = "name: comment/description [type]" if output_name_first else "'comment/description' (name) [type]"
        logger.info("Available outputs: format is: `{}`".format(fmt))
        for o in outputs:
            # Note: we can't do a `dry` config because some layer and field names can be validated only if we
            # load the schematic and the PCB.
            if do_config:
                config_output(o, dry=False)
            if output_name_first:
                logger.info('- {}: {} [{}]'.format(o.name, o.comment, o.type))
            else:
                logger.info('- '+str(o))
        logger.info("")
    if groups and not only_pre:
        logger.info("Available groups:")
        for g, items in groups.items():
            logger.info('- '+g+': '+', '.join(items))
        logger.info("")
    if pf:
        logger.info("You can use e.g. `kibot --skip-pre preflight_name1,preflight_name2` to")
        logger.info("skip specific preflights (or pass `all` to skip them all).")
        logger.info("")
    if outputs:
        logger.info("You can use e.g. `kibot output_name1 output_name2` to generate only")
        logger.info("specific outputs by name.")
        logger.info("")
    if groups:
        logger.info("You can use the name of a group instead of an output name.")
        logger.info("")


def list_variants(logger, only_names):
    variants = RegOutput.get_variants()
    if not variants:
        if not only_names:
            logger.info('No variants defined')
        return
    if only_names:
        for name in sorted(variants.keys()):
            logger.info(name)
        return
    logger.info("Available variants: 'comment/description' (name) [type]")
    for name in sorted(variants.keys()):
        logger.info('- '+str(variants[name]))


def solve_config(a_plot_config, quiet=False):
    plot_config = a_plot_config
    if not plot_config:
        plot_configs = glob('*.kibot.yaml')+glob('*.kiplot.yaml')+glob('*.kibot.yaml.gz')
        if len(plot_configs) == 1:
            plot_config = plot_configs[0]
            if not quiet:
                logger.info('Using config file: '+os.path.relpath(plot_config))
        elif len(plot_configs) > 1:
            plot_config = plot_configs[0]
            logger.warning(W_VARCFG + 'More than one config file found in current directory.\n'
                           '  Using '+plot_config+' if you want to use another use -c option.')
        else:
            logger.error('No config file found (*.kibot.yaml), use -c to specify one.')
            sys.exit(EXIT_BAD_ARGS)
    if not os.path.isfile(plot_config):
        logger.error("Plot config file not found: "+plot_config)
        sys.exit(EXIT_BAD_ARGS)
    logger.debug('Using configuration file: `{}`'.format(plot_config))
    return plot_config


def set_locale():
    """ Try to set the locale for all the cataegories.
        If it fails try with LC_NUMERIC (the one we need for tests). """
    try:
        locale.setlocale(locale.LC_ALL, '')
        return
    except locale.Error:
        pass
    try:
        locale.setlocale(locale.LC_NUMERIC, '')
        return
    except locale.Error:
        pass


def detect_kicad():
    try:
        import pcbnew
    except ImportError:
        logger.error("Failed to import pcbnew Python module."
                     " Is KiCad installed?"
                     " Do you need to add it to PYTHONPATH?")
        logger.error(TRY_INSTALL_CHECK)
        sys.exit(NO_PCBNEW_MODULE)
    try:
        GS.kicad_version = pcbnew.GetBuildVersion()
    except AttributeError:
        logger.warning(W_NOKIVER+"Unknown KiCad version, please install KiCad 5.1.6 or newer")
        # Assume the best case
        GS.kicad_version = '5.1.5'
    try:
        # Debian sid may 2021 mess:
        really_index = GS.kicad_version.index('really')
        GS.kicad_version = GS.kicad_version[really_index+6:]
    except ValueError:
        pass

    m = re.search(r'(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?', GS.kicad_version)
    if m is None:
        logger.error("Unable to detect KiCad version, got: `{}`".format(GS.kicad_version))
        sys.exit(NO_PCBNEW_MODULE)
    GS.kicad_version_major = int(m.group(1))
    GS.kicad_version_minor = int(m.group(2))
    GS.kicad_version_patch = int(m.group(3))
    GS.kicad_version_subpatch = 0 if m.group(4) is None else int(m.group(4))
    GS.kicad_version_n = (GS.kicad_version_major*10000000+GS.kicad_version_minor*10000+GS.kicad_version_patch*10 +
                          GS.kicad_version_subpatch)
    GS.ki5 = GS.kicad_version_major < 6
    GS.ki6 = GS.kicad_version_major >= 6
    GS.ki6_only = GS.kicad_version_major == 6
    GS.ki7 = GS.kicad_version_major >= 7
    GS.ki8 = (GS.kicad_version_major == 7 and GS.kicad_version_minor >= 99) or GS.kicad_version_major >= 8
    GS.footprint_gr_type = 'MGRAPHIC' if not GS.ki8 else 'PCB_SHAPE'
    GS.board_gr_type = 'DRAWSEGMENT' if GS.ki5 else 'PCB_SHAPE'
    GS.footprint_update_local_coords = GS.dummy1 if GS.ki8 else GS.footprint_update_local_coords_ki7
    logger.debug('Detected KiCad v{}.{}.{} ({} {})'.format(GS.kicad_version_major, GS.kicad_version_minor,
                 GS.kicad_version_patch, GS.kicad_version, GS.kicad_version_n))
    # Used to look for plug-ins.
    # KICAD_PATH isn't good on my system.
    # The kicad-nightly package overwrites the regular package!!
    GS.kicad_share_path = '/usr/share/kicad'
    if GS.ki6:
        GS.kicad_conf_path = pcbnew.GetSettingsManager().GetUserSettingsPath()
        if nightly:
            # Nightly Debian packages uses `/usr/share/kicad-nightly/kicad-nightly.env` as an environment extension
            # This script defines KICAD_CONFIG_HOME="$HOME/.config/kicadnightly"
            # So we just patch it, as we patch the name of the binaries
            # No longer needed for 202112021512+6.0.0+rc1+287+gbb08ef2f41+deb11
            # GS.kicad_conf_path = GS.kicad_conf_path.replace('/kicad/', '/kicadnightly/')
            GS.kicad_share_path = GS.kicad_share_path.replace('/kicad/', '/kicad-nightly/')
            GS.kicad_dir = 'kicad-nightly'
        GS.pro_ext = '.kicad_pro'
        # KiCad 6 doesn't support the Rescue layer
        GS.work_layer = 'User.9'
    else:
        # Bug in KiCad (#6989), prints to stderr:
        # `../src/common/stdpbase.cpp(62): assert "traits" failed in Get(test_dir): create wxApp before calling this`
        # Found in KiCad 5.1.8, 5.1.9
        # So we temporarily suppress stderr
        with hide_stderr():
            GS.kicad_conf_path = pcbnew.GetKicadConfigPath()
        GS.pro_ext = '.pro'
        GS.work_layer = 'Rescue'
    # Dirs to look for plugins
    GS.kicad_plugins_dirs = []
    # /usr/share/kicad/*
    GS.kicad_plugins_dirs.append(os.path.join(GS.kicad_share_path, 'scripting'))
    GS.kicad_plugins_dirs.append(os.path.join(GS.kicad_share_path, 'scripting', 'plugins'))
    GS.kicad_plugins_dirs.append(os.path.join(GS.kicad_share_path, '3rdparty', 'plugins'))  # KiCad 6.0 PCM
    # ~/.config/kicad/*
    GS.kicad_plugins_dirs.append(os.path.join(GS.kicad_conf_path, 'scripting'))
    GS.kicad_plugins_dirs.append(os.path.join(GS.kicad_conf_path, 'scripting', 'plugins'))
    # ~/.kicad_plugins and ~/.kicad
    if 'HOME' in os.environ:
        home = os.environ['HOME']
        GS.kicad_plugins_dirs.append(os.path.join(home, '.kicad_plugins'))
        GS.kicad_plugins_dirs.append(os.path.join(home, '.kicad', 'scripting'))
        GS.kicad_plugins_dirs.append(os.path.join(home, '.kicad', 'scripting', 'plugins'))
        if GS.kicad_version_major >= 6:
            ver_dir = str(GS.kicad_version_major)+'.'+str(GS.kicad_version_minor)
            local_share = os.path.join(home, '.local', 'share', 'kicad', ver_dir)
            GS.kicad_plugins_dirs.append(os.path.join(local_share, 'scripting'))
            GS.kicad_plugins_dirs.append(os.path.join(local_share, 'scripting', 'plugins'))
            GS.kicad_plugins_dirs.append(os.path.join(local_share, '3rdparty', 'plugins'))   # KiCad 6.0 PCM
    if GS.debug_level > 1:
        logger.debug('KiCad config path {}'.format(GS.kicad_conf_path))


def parse_defines(args):
    for define in args.define:
        if '=' not in define:
            logger.error('Malformed `define` option, must be VARIABLE=VALUE ({})'.format(define))
            sys.exit(EXIT_BAD_ARGS)
        var = define.split('=')[0]
        GS.cli_defines[var] = define[len(var)+1:]


def parse_global_redef(args):
    for redef in args.global_redef:
        if '=' not in redef:
            logger.error('Malformed global-redef option, must be VARIABLE=VALUE ({})'.format(redef))
            sys.exit(EXIT_BAD_ARGS)
        var = redef.split('=')[0]
        GS.cli_global_defs[var] = redef[len(var)+1:]


class SimpleFilter(object):
    def __init__(self, num):
        self.number = num
        self.regex = re.compile('')
        self.error = ''


def apply_warning_filter(args):
    if args.no_warn:
        try:
            log.set_filters([SimpleFilter(int(n)) for n in args.no_warn.split(',')])
        except ValueError:
            logger.error('-w/--no-warn must specify a comma separated list of numbers ({})'.format(args.no_warn))
            sys.exit(EXIT_BAD_ARGS)


def debug_arguments(args):
    if GS.debug_level > 1:
        logger.debug('Command line arguments:\n'+str(sys.argv))
        logger.debug('Command line parsed:\n'+str(args))


def detect_windows():
    if platform.system() != 'Windows':
        return
    # Note: We assume this is the Python from KiCad, but we should check it ...
    GS.on_windows = True
    logger.warning(W_ONWIN+'Running on Windows, this is experimental, please report any problem')


def main():
    set_locale()
    ver = 'KiBot '+__version__+' - '+__copyright__+' - License: '+__license__
    GS.out_dir_in_cmd_line = '-d' in sys.argv or '--out-dir' in sys.argv
    args = docopt(__doc__, version=ver, options_first=True)

    # Set the specified verbosity
    GS.debug_enabled = log.set_verbosity(logger, args.verbose, args.quiet)
    log.debug_level = GS.debug_level = args.verbose
    # We can log all the debug info to a separated file
    if args.log:
        if os.path.isfile(args.log):
            os.remove(args.log)
        else:
            os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
        log.set_file_log(args.log)
        GS.debug_level = 10
    # The log setup finished, this is our first log message
    logger.debug('KiBot {} verbose level: {} started on {}'.format(__version__, args.verbose, datetime.now()))
    apply_warning_filter(args)
    # Now we have the debug level set we can check (and optionally inform) KiCad info
    detect_kicad()
    detect_windows()
    debug_arguments(args)

    # Force iBoM to avoid the use of graphical stuff
    os.environ['INTERACTIVE_HTML_BOM_NO_DISPLAY'] = 'True'

    # Parse global overwrite options
    parse_global_redef(args)

    # Disable auto-download if needed
    if args.no_auto_download:
        dep_downloader.disable_auto_download = True

    # Output dir: relative to CWD (absolute path overrides)
    GS.out_dir = os.path.join(os.getcwd(), args.out_dir)

    # Load output and preflight plugins
    load_actions()

    if args.banner is not None:
        try:
            id = int(args.banner)
        except ValueError:
            logger.error('The banner option needs an integer ({})'.format(id))
            sys.exit(EXIT_BAD_ARGS)
        logger.info(get_banner(id))

    if args.help_outputs or args.help_list_outputs:
        print_outputs_help(args.rst, details=args.help_outputs)
        sys.exit(0)
    if args.help_output:
        print_output_help(args.help_output)
        sys.exit(0)
    if args.help_preflights:
        print_preflights_help(args.rst)
        sys.exit(0)
    if args.help_variants:
        print_variants_help(args.rst)
        sys.exit(0)
    if args.help_filters:
        print_filters_help(args.rst)
        sys.exit(0)
    if args.help_global_options:
        print_global_options_help(args.rst)
        sys.exit(0)
    if args.help_dependencies:
        print_dependencies(args.markdown, args.json, args.rst)
        sys.exit(0)
    if args.help_banners:
        for c, b in enumerate(BANNERS):
            logger.info('Banner '+str(c))
            logger.info(b)
        sys.exit(0)
    if args.help_errors:
        print_errors(args.rst)
        sys.exit(0)
    if args.example:
        check_board_file(args.board_file)
        if args.copy_options and not args.board_file:
            logger.error('Asked to copy options but no PCB specified.')
            sys.exit(EXIT_BAD_ARGS)
        create_example(args.board_file, GS.out_dir, args.copy_options, args.copy_and_expand)
        sys.exit(0)
    if args.quick_start:
        # Some kind of wizard to get usable examples
        generate_examples(args.start, args.dry, args.type)
        sys.exit(0)

    # Determine the YAML file
    plot_config = solve_config(args.plot_config, args.only_names)
    if not (args.list or args.list_variants) or args.config_outs:
        # Determine the SCH file
        GS.set_sch(solve_schematic('.', args.schematic, args.board_file, plot_config))
        # Determine the PCB file
        GS.set_pcb(solve_board_file('.', args.board_file))
        # Determine the project file
        GS.set_pro(solve_project_file())

    # Parse preprocessor defines
    parse_defines(args)

    # Read the config file
    cr = CfgYamlReader()
    outputs = None
    try:
        # The Python way ...
        with gzip.open(plot_config, mode='rt') as cf_file:
            try:
                outputs = cr.read(cf_file)
            except KiPlotConfigurationError as e:
                config_error(str(e))
    except OSError:
        pass
    if outputs is None:
        with open(plot_config) as cf_file:
            try:
                outputs = cr.read(cf_file)
            except KiPlotConfigurationError as e:
                config_error(str(e))

    # Is just "list the available targets"?
    if args.list:
        list_pre_and_outs(logger, outputs, args.config_outs, args.only_names, args.only_pre, args.only_groups,
                          args.output_name_first)
        sys.exit(0)

    if args.list_variants:
        list_variants(logger, args.only_names)
        sys.exit(0)

    if args.makefile:
        # Only create a makefile
        generate_makefile(args.makefile, plot_config, outputs)
    else:
        # Do all the job (preflight + outputs)
        generate_outputs(outputs, args.target, args.invert_sel, args.skip_pre, args.cli_order, args.no_priority,
                         dont_stop=args.dont_stop)
    # Print total warnings
    logger.log_totals()


if __name__ == "__main__":
    main()  # pragma: no cover
