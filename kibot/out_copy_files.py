# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024 Salvador E. Tropea
# Copyright (c) 2022-2024 Instituto Nacional de Tecnología Industrial
# License: AGPL-3.0
# Project: KiBot (formerly KiPlot)
from copy import copy
import fnmatch
import glob
import os
import re
from shutil import copy2
from .error import KiPlotConfigurationError
from .gs import GS
from .kiplot import config_output, get_output_dir, run_output, register_xmp_import
from .kicad.config import KiConf, LibAlias, FP_LIB_TABLE, SYM_LIB_TABLE
from .misc import WRONG_ARGUMENTS, INTERNAL_ERROR, W_COPYOVER, W_MISSLIB, W_MISSCMP
from .optionable import Optionable
from .out_base_3d import Base3DOptions
from .registrable import RegOutput
from .macros import macros, document, output_class  # noqa: F401
from . import log

logger = log.get_logger()


def may_be_rel(file):
    rel_file = os.path.relpath(file)
    if len(rel_file) < len(file):
        return rel_file
    return file


class FilesList(Optionable):
    def __init__(self):
        super().__init__()
        with document:
            self.source = '*'
            """ *For the `files` and `out_files` mode this is th file names to add,
                wildcards allowed. Use ** for recursive match.
                For the `output` mode this is the name of the output.
                For the `3d_models` is a pattern to match the name of the 3D models extracted from the PCB.
                Not used for the `project` mode """
            self.source_type = 'files'
            """ *[files,out_files,output,3d_models,project] From where do we get the files to be copied.
                `files`: files relative to the current working directory.
                `out_files`: files relative to output dir specified with `-d` command line option.
                `output`: files generated by the output specified by `source`.
                `3d_models`: 3D models used in the project.
                `project`: schematic, PCB, footprints, symbols, 3D models and project files (KiCad 6+) """
            self.filter = '.*'
            """ A regular expression that source files must match.
                Not used for the `project` mode """
            self.dest = ''
            """ Destination directory inside the output dir, empty means the same of the file
                relative to the source directory.
                Note that when you specify a name here files are copied to this destination
                without creating subdirs. The `project` mode is an exception.
                For the `3d_models` type you can use DIR+ to create subdirs under DIR """
            self.save_pcb = False
            """ Only usable for the `3d_models` mode.
                Save a PCB copy modified to use the copied 3D models.
                You don't need to specify it for `project` mode """
        self._append_mode = False

    def apply_rename(self, fname):
        if self.dest and not self._append_mode:
            # A destination specified by the user
            dest = os.path.basename(fname)
        else:
            for d in self.rel_dirs:
                if d is not None and fname.startswith(d):
                    dest = os.path.relpath(fname, d)
                    break
            else:
                dest = os.path.basename(fname)
        res = '${KIPRJMOD}/'+os.path.join(self.output_dir, dest)
        return res


class Copy_FilesOptions(Base3DOptions):
    def __init__(self):
        with document:
            self.files = FilesList
            """ *[list(dict)] Which files will be included """
            self.follow_links = True
            """ Store the file pointed by symlinks, not the symlink """
            self.link_no_copy = False
            """ Create symlinks instead of copying files """
        super().__init__()
        self._expand_id = 'copy'
        self._expand_ext = 'files'

    def config(self, parent):
        super().config(parent)
        if isinstance(self.files, type):
            raise KiPlotConfigurationError('No files provided')

    def get_from_output(self, f, no_out_run):
        from_output = f.source
        logger.debugl(2, '- From output `{}`'.format(from_output))
        out = RegOutput.get_output(from_output)
        if out is not None:
            config_output(out)
            out_dir = get_output_dir(out.dir, out, dry=True)
            files_list = out.get_targets(out_dir)
            logger.debugl(2, '- List of files: {}'.format(files_list))
        else:
            GS.exit_with_error(f'Unknown output `{from_output}` selected in {self._parent}', WRONG_ARGUMENTS)
        # Check if we must run the output to create the files
        if not no_out_run:
            for file in files_list:
                if not os.path.isfile(file):
                    # The target doesn't exist
                    if not out._done:
                        # The output wasn't created in this run, try running it
                        run_output(out)
                    if not os.path.isfile(file):
                        # Still missing, something is wrong
                        GS.exit_with_error(f'Unable to generate `{file}` from {out}', INTERNAL_ERROR)
        return files_list

    def copy_footprints(self, dest, dry):
        out_lib_base = os.path.join(self.output_dir, dest, 'footprints')
        out_lib_base_prj = os.path.join('${KIPRJMOD}', 'footprints')
        aliases = {}
        extra_files = []
        added = set()
        for m in GS.get_modules():
            id = m.GetFPID()
            lib_nick = str(id.GetLibNickname())
            src_alias = KiConf.fp_nick_to_path(lib_nick)
            if src_alias is None:
                logger.warning(f'{W_MISSLIB}Missing footprint library `{lib_nick}`')
                continue
            src_lib = src_alias.uri
            out_lib = os.path.join(out_lib_base, lib_nick)
            out_lib = GS.create_fp_lib(out_lib)
            if lib_nick not in aliases:
                new_alias = copy(src_alias)
                new_alias.uri = os.path.join(out_lib_base_prj, lib_nick+'.pretty')
                aliases[lib_nick] = new_alias

            name = str(id.GetLibItemName())
            mod_fname = name+'.kicad_mod'
            footprint_src = os.path.join(src_lib, mod_fname)
            if not os.path.isfile(footprint_src):
                logger.warning(f'{W_MISSCMP}Missing footprint `{name}` ({lib_nick}:{name})')
            elif footprint_src not in added:
                footprint_dst = os.path.join(out_lib, mod_fname)
                extra_files.append((footprint_src, footprint_dst))
                added.add(footprint_src)
        table_fname = os.path.join(self.output_dir, dest, FP_LIB_TABLE)
        extra_files.append(table_fname)
        if not dry:
            KiConf.save_fp_lib_aliases(table_fname, aliases)
        return extra_files

    def copy_symbols(self, dest, dry):
        extra_files = []
        if not GS.sch:
            return extra_files
        out_lib_base = os.path.join(self.output_dir, dest, 'symbols')
        out_lib_base_prj = os.path.join('${KIPRJMOD}', 'symbols')
        aliases = {}
        # Split the collected components into separated libs
        libs = {}
        for obj in GS.sch.lib_symbol_names.values():
            lib = obj.lib if obj.lib else 'locally_edited'
            libs.setdefault(lib, []).append(obj.name)
        table_fname = os.path.join(self.output_dir, dest, SYM_LIB_TABLE)
        extra_files.append(table_fname)
        if dry:
            for lib in libs.keys():
                if lib != 'locally_edited':
                    extra_files.append(os.path.join(out_lib_base, lib+'.kicad_sym'))
        else:
            # Create the libs
            for lib, comps in libs.items():
                if lib == 'locally_edited':
                    # Not from a lib, just a copy inside the SCH
                    continue
                GS.sch.write_lib(out_lib_base, lib, comps)
                new_alias = LibAlias()
                new_alias.name = lib
                new_alias.legacy = False
                new_alias.type = 'KiCad'
                new_alias.options = new_alias.descr = ''
                new_alias.uri = os.path.join(out_lib_base_prj, lib+'.kicad_sym')
                aliases[lib] = new_alias
                extra_files.append(os.path.join(out_lib_base, lib+'.kicad_sym'))
            # Create the sym-lib-table
            KiConf.save_fp_lib_aliases(table_fname, aliases, is_fp=False)
        return extra_files

    def add_sch_files(self, files, dest_dir):
        for f in GS.sch.get_files():
            files.append(os.path.join(dest_dir, os.path.relpath(f, GS.sch_dir)))

    def get_3d_models(self, f, mode_project, dry):
        """ Look for the 3D models and make a list, optionally download them """
        extra_files = []
        GS.check_pcb()
        GS.load_board()
        if mode_project:
            # From the PCB point this is just the 3D models dir
            f.output_dir = '3d_models'
            f._append_mode = True
        else:
            dest_dir = f.dest
            f._append_mode = False
            if dest_dir and dest_dir[-1] == '+':
                dest_dir = dest_dir[:-1]
                f._append_mode = True
            f.output_dir = dest_dir
        # Apply any variant
        self.filter_pcb_components(do_3D=True, do_2D=True)
        # Download missing models and rename all collected 3D models (renamed)
        f.rel_dirs = self.rel_dirs
        files_list = self.download_models(rename_filter=f.source, rename_function=FilesList.apply_rename, rename_data=f)

        if f.save_pcb or mode_project:
            dest_dir = self.output_dir
            if mode_project:
                dest_dir = os.path.join(dest_dir, f.dest)
                os.makedirs(dest_dir, exist_ok=True)
            fname = os.path.join(dest_dir, os.path.basename(GS.pcb_file))
            if not dry:
                logger.debug('Saving the PCB to '+fname)
                GS.board.Save(fname)
                if mode_project:
                    GS.check_sch()
                    logger.debug('Saving the schematic to '+dest_dir)
                    GS.sch.save_variant(dest_dir)
                    self.add_sch_files(extra_files, dest_dir)
            elif mode_project:
                self.add_sch_files(extra_files, dest_dir)
            prj_name, prl_name, dru_name = GS.copy_project(fname, dry)
            # Extra files that we are generating
            extra_files.append(fname)
            if prj_name:
                extra_files.append(prj_name)
            if prl_name:
                extra_files.append(prl_name)
            if dru_name:
                extra_files.append(dru_name)
            # Worksheet
            prj_name_used = prj_name
            if dry and not os.path.isfile(prj_name_used):
                prj_name_used = GS.pro_file
            wks = GS.fix_page_layout(prj_name_used, dry=dry)
            extra_files += [w for w in wks if w]
            if mode_project:
                extra_files += self.copy_footprints(f.dest, dry)
                extra_files += self.copy_symbols(f.dest, dry)
        if not self._comps:
            # We must undo the download/rename
            self.undo_3d_models_rename(GS.board)
        else:
            self.unfilter_pcb_components(do_3D=True, do_2D=True)
        # Also include the step/wrl counterpart
        new_list = []
        for fn in files_list:
            if fn.endswith('.wrl'):
                fn = fn[:-4]+'.step'
                if os.path.isfile(fn) and fn not in files_list:
                    new_list.append(fn)
            elif fn.endswith('.step'):
                fn = fn[:-5]+'.wrl'
                if os.path.isfile(fn) and fn not in files_list:
                    new_list.append(fn)
        if mode_project:
            # From the output point this needs to add the destination dir
            f.output_dir = os.path.join(f.dest, f.output_dir)
        return files_list+fnmatch.filter(new_list, f.source), extra_files

    def get_files(self, no_out_run=False):
        files = []
        # The source file can be relative to the current directory or to the output directory
        src_dir_cwd = os.getcwd()
        src_dir_outdir = self.expand_filename_sch(GS.out_dir)
        # Initialize the config class so we can know where are the 3D models at system level
        KiConf.init(GS.pcb_file)
        # List of base paths
        self.rel_dirs = []
        if KiConf.models_3d_dir:
            self.rel_dirs.append(os.path.normpath(os.path.join(GS.pcb_dir, KiConf.models_3d_dir)))
        if KiConf.party_3rd_dir:
            self.rel_dirs.append(os.path.normpath(os.path.join(GS.pcb_dir, KiConf.party_3rd_dir)))
        self.rel_dirs.append(GS.pcb_dir)
        # Process each file specification expanding it to real files
        for f in self.files:
            src_dir = src_dir_outdir if f.source_type == 'out_files' or f.source_type == 'output' else src_dir_cwd
            mode_project = f.source_type == 'project'
            if mode_project and not GS.ki6:
                raise KiPlotConfigurationError('The `project` mode needs KiCad 6 or newer')
            mode_3d = f.source_type == '3d_models'
            # Get the list of candidates
            files_list = None
            extra_files = []
            if f.source_type == 'output':
                # The files are generated by a KiBot output
                files_list = self.get_from_output(f, no_out_run)
            elif mode_3d or mode_project:
                # The files are 3D models
                files_list, extra_files = self.get_3d_models(f, mode_project, no_out_run)
            else:  # files and out_files
                # Regular files
                source = f.expand_filename_both(f.source, make_safe=False)
                files_list = glob.iglob(os.path.join(src_dir, source), recursive=True)
                if GS.debug_level > 1:
                    files_list = list(files_list)
                    logger.debug('- Pattern {} list of files: {}'.format(source, files_list))
            # Filter and adapt them
            fil = re.compile(f.filter)
            for fname in filter(fil.match, files_list):
                fname_real = os.path.realpath(fname) if self.follow_links else os.path.abspath(fname)
                # Compute the destination directory
                dest = fname
                is_abs = os.path.isabs(fname)
                if f.dest and not f._append_mode:
                    # A destination specified by the user
                    # All files goes to the same destination directory
                    dest = os.path.join(f.dest, os.path.basename(fname))
                elif (mode_3d or mode_project) and is_abs:
                    for d in self.rel_dirs:
                        if d is not None and fname.startswith(d):
                            dest = os.path.relpath(dest, d)
                            break
                    else:
                        dest = os.path.basename(fname)
                    if f._append_mode:
                        dest = os.path.join(f.output_dir, dest)
                else:
                    dest = os.path.relpath(dest, src_dir)
                files.append((fname_real, dest))
            # Process the special extra files
            for f in extra_files:
                if isinstance(f, str):
                    if fil.match(f):
                        files.append((None, f))
                else:
                    if fil.match(f[0]):
                        files.append(f)
        return files

    def get_targets(self, out_dir):
        self.output_dir = out_dir
        files = self.get_files(no_out_run=True)
        return sorted([os.path.join(out_dir, v) for _, v in files])

    def get_dependencies(self):
        files = self.get_files(no_out_run=True)
        return sorted([v for v, _ in files if v is not None])

    def run(self, output):
        super().run(output)
        # Output file name
        logger.debug('Collecting files')
        # Collect the files
        files = self.get_files()
        logger.debug('Copying files')
        output += os.path.sep
        copied = {}
        for (src, dst) in files:
            if src is None:
                # Files we generate, we don't need to copy them
                continue
            dest = os.path.join(output, dst)
            dest_dir = os.path.dirname(dest)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            logger.debug('- {} -> {}'.format(src, dest))
            if dest in copied:
                logger.warning(W_COPYOVER+'`{}` and `{}` both are copied to `{}`'.
                               format(may_be_rel(src), may_be_rel(copied[dest]), may_be_rel(dest)))
            try:
                if os.path.samefile(src, dest):
                    raise KiPlotConfigurationError('Trying to copy {} over itself {}'.format(src, dest))
            except FileNotFoundError:
                pass
            if os.path.isfile(dest) or os.path.islink(dest):
                os.remove(dest)
            if self.link_no_copy:
                os.symlink(os.path.relpath(src, os.path.dirname(dest)), dest)
            else:
                copy2(src, dest)
            copied[dest] = src
        # Remove the downloaded 3D models
        self.remove_temporals()


@output_class
class Copy_Files(BaseOutput):  # noqa: F821
    """ Files copier
        Used to copy files to the output directory.
        Useful when an external tool is used to compress the output directory.
        Note that you can use the `compress` output to create archives """
    def __init__(self):
        super().__init__()
        # Make it low priority so it gets created after all the other outputs
        self.priority = 11
        with document:
            self.options = Copy_FilesOptions
            """ *[dict] Options for the `copy_files` output """
        # The help is inherited and already mentions the default priority
        self.fix_priority_help()
        # Mostly oriented to the project copy
        self._category = ['PCB/docs', 'Schematic/docs']
        self._any_related = True

    def get_dependencies(self):
        return self.options.get_dependencies()

    @staticmethod
    def get_conf_examples(name, layers):
        if GS.pcb_file and GS.sch_file and GS.pro_file:
            # Add it only when we have a full project
            register_xmp_import('ExportProject')
        return []

    def run(self, output_dir):
        # No output member, just a dir
        self.options.output_dir = output_dir
        self.options.run(output_dir)
