# -*- coding: utf-8 -*-
# Copyright (c) 2021 Salvador E. Tropea
# Copyright (c) 2021 Instituto Nacional de Tecnología Industrial
# License: GPL-3.0
# Project: KiBot (formerly KiPlot)
import os
import re
import requests
from .out_base import VariantOptions
from .fil_base import DummyFilter
from .error import KiPlotConfigurationError
from .misc import W_UNKFLD, W_ALRDOWN, W_FAILDL, USER_AGENT
from .gs import GS
from .macros import macros, document, output_class  # noqa: F401
from . import log
logger = log.get_logger()


def is_url(ds):
    return ds.startswith('http://') or ds.startswith('https://')


class Download_Datasheets_Options(VariantOptions):
    _vars_regex = re.compile(r'\$\{([^\}]+)\}')

    def __init__(self):
        super().__init__()
        with document:
            self.field = 'Datasheet'
            """ *Name of the field containing the URL """
            self.output = '${VALUE}.pdf'
            """ Name used for the downloaded datasheet.
                ${FIELD} will be replaced by the FIELD content """
            self.dnf = False
            """ Include the DNF components """
            self.repeated = False
            """ Download URLs that we already downloaded.
                It only makes sense if the `output` field makes their output different """
            self.link_repeated = True
            """ Instead of download things we already downloaded use symlinks """
        # Used to collect the targets
        self._dry = False
        self._unknown_is_error = True

    def config(self, parent):
        super().config(parent)
        if not self.field:
            raise KiPlotConfigurationError("Empty `field` ({})".format(str(self._tree)))
        if not self.output:
            raise KiPlotConfigurationError("Empty `output` ({})".format(str(self._tree)))
        self.field = self.field.lower()

    def do_warning(self, msg, ds, c):
        logger.warning(W_FAILDL+'{} during download of `{}` [{}]'.format(msg, ds, c.ref))
        return None

    def download(self, c, ds, dir, name, known):
        dest = os.path.join(dir, name)
        logger.debug('To download: {} -> {}'.format(ds, dest))
        if name in self._downloaded:
            logger.warning(W_ALRDOWN+'Datasheet `{}` already downloaded'.format(name))
            return None
        elif known is not None and self.link_repeated:
            # We already downloaded this URL, but stored it with a different name
            if not self._dry:
                os.symlink(known, dest)
            self._created.append(os.path.relpath(dest))
        elif not os.path.isfile(dest):
            # Download
            if not self._dry:
                try:
                    r = requests.get(ds, allow_redirects=True, headers={'User-Agent': USER_AGENT}, timeout=20)
                except requests.exceptions.ReadTimeout:
                    return self.do_warning('Timeout', ds, c)
                except requests.exceptions.SSLError:
                    return self.do_warning('SSL Error', ds, c)
                except requests.exceptions.TooManyRedirects:
                    return self.do_warning('More than 30 redirections', ds, c)
                except requests.exceptions.ConnectionError:
                    return self.do_warning('Connection', ds, c)
                except requests.exceptions.RequestException as e:
                    return self.do_warning(str(e), ds, c)
                if r.status_code != 200:
                    return self.do_warning('Failed with status '+str(r.status_code), ds, c)
                with open(dest, 'wb') as f:
                    f.write(r.content)
            self._downloaded.add(name)
            self._created.append(os.path.relpath(dest))
        elif self._dry:
            self._created.append(os.path.relpath(dest))
        return name

    def out_name(self, c):
        """ Compute the name of the output file.
            Replaces ${FIELD} and %X. """
        out = ''
        last = 0
        pattern = self.output
        pattern_l = len(pattern)
        for match in Download_Datasheets_Options._vars_regex.finditer(pattern):
            fname = match.group(1).lower()
            value = c.get_field_value(fname)
            if value is None:
                value = 'Unknown'
                logger.warning(W_UNKFLD+"In datasheets download output file name:"
                               " Field `{}` not defined for {}, using `Unknown`".format(fname, c.ref))
            if match.start():
                out += pattern[last:match.start()]
            out += value
            last = match.end()
        if last < pattern_l:
            out += pattern[last:pattern_l]
        out = self.expand_filename_sch(out)
        return out.replace('/', '_')

    def run(self, output_dir):
        if not self.dnf_filter and not self.variant:
            # Add a dummy filter to force the creation of a components list
            self.dnf_filter = DummyFilter()
        super().run(output_dir)
        self._urls = {}
        self._downloaded = set()
        self._created = []
        field_used = False
        for c in self._comps:
            ds = c.get_field_value(self.field)
            if ds is not None:
                field_used = True
            if not c.included or (not c.fitted and not self.dnf):
                continue
            if ds and is_url(ds):
                known = self._urls.get(ds, None)
                if known is None or self.repeated:
                    name = self.out_name(c)
                    name = self.download(c, ds, output_dir, name, known)
                    if known is None:
                        self._urls[ds] = name
                else:
                    logger.debug('Already downloaded: '+ds)
        if not field_used:
            known_fields = GS.sch.get_field_names({})
            if self.field not in known_fields:
                logger.warning(W_UNKFLD+"The field used for datasheets ({}) doesn't seem to be used".format(self.field))
        else:
            logger.debug('Unique URLs: '+str(len(self._urls)))
            logger.debug('Downloaded: '+str(len(self._downloaded)))
            logger.debug('Created: '+str(len(self._created)))

    def get_targets(self, out_dir):
        # Do a dry run to collect the output names
        self._dry = True
        self.run(out_dir)
        self._dry = False
        return self._created


@output_class
class Download_Datasheets(BaseOutput):  # noqa: F821
    """ Datasheets downloader
        Downloads the datasheets for the project """
    def __init__(self):
        super().__init__()
        with document:
            self.options = Download_Datasheets_Options
            """ *[dict] Options for the `download_datasheets` output """
        self._sch_related = True
        self._category = 'Schematic/docs'

    def run(self, output_dir):
        # No output member, just a dir
        self.options.run(output_dir)

    @staticmethod
    def get_conf_examples(name, layers, templates):
        has_urls = False
        for c in GS.sch.get_components():
            if c.datasheet and is_url(c.datasheet):
                has_urls = True
                break
        if not has_urls:
            return None
        return BaseOutput.simple_conf_examples(name, 'Download the datasheets', 'Datasheets')  # noqa: F821
