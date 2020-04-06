# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals
import os
import os.path
import io
import json
from pkg_resources import resource_filename

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.engine.url import (
    URL as EngineURL,
    make_url as make_engine_url)
import transaction

from .. import db
from ..package import pkginfo
from ..component import Component
from ..lib.config import Option
from ..models import DBSession
from ..i18n import Localizer, Translations

from .util import _
from .model import Base, Setting
from .command import BackupCommand  # NOQA
from .backup import BackupBase  # NOQA


class CoreComponent(Component):
    identity = 'core'
    metadata = Base.metadata

    def __init__(self, env, settings):
        super(CoreComponent, self).__init__(env, settings)
        self.locale_default = None
        self.debug = False

    def initialize(self):
        Component.initialize(self)

        self.debug = self.options['debug']
        self.locale_default = self.options['locale.default']
        self.locale_available = self.options['locale.available']

        opt_db = self.options.with_prefix('database')
        sa_url = self._engine_url()

        self.engine = create_engine(sa_url)
        self._sa_engine = self.engine

        if opt_db['check_at_startup']:
            conn = self._sa_engine.connect()
            conn.close()

        DBSession.configure(bind=self._sa_engine)

        self.DBSession = DBSession

        # Methods for customization in components
        self.support_url_view = lambda request: self.options['support_url']

    def is_service_ready(self):
        while True:
            try:
                sa_url = self._engine_url(error_on_pwfile=True)
                break
            except FileNotFoundError as exc:
                yield "File [{}] is missing!".format(exc.filename)

        sa_engine = create_engine(sa_url)
        while True:
            try:
                conn = sa_engine.connect()
                break
            except OperationalError as exc:
                yield str(exc.orig).rstrip()
        conn.close()

    def initialize_db(self):
        for k, v in (
            ('system.name', 'NextGIS Web'),
            ('system.full_name', self.localizer().translate(
                _('NextGIS geoinformation system'))),
            ('units', 'metric'),
            ('degree_format', 'dd'),
            ('measurement_srid', 4326),
        ):
            self.init_settings(self.identity, k, self._settings.get(k, v))

    def gtsdir(self, comp):
        """ Get component's file storage folder """
        return os.path.join(self.options['sdir'], comp.identity) \
            if 'sdir' in self.options else None

    def mksdir(self, comp):
        """ Create file storage folder """
        self.bmakedirs(self.options['sdir'], comp.identity)

    def bmakedirs(self, base, path):
        fpath = os.path.join(base, path)
        if os.path.isdir(fpath):
            return

        if not os.path.isdir(base):
            raise IOError("Invalid base directory path")

        os.makedirs(fpath)

    def localizer(self, locale=None):
        if locale is None:
            locale = self.locale_default
        if not hasattr(self, '_localizer'):
            self._localizer = dict()
        if locale in self._localizer:
            return self._localizer[locale]

        translations = Translations()
        for pkg in pkginfo.packages:
            translations.scandir(resource_filename(pkg, 'locale'), locale)

        lobj = Localizer(locale, translations)
        self._localizer[locale] = lobj
        return lobj

    def settings_exists(self, component, name):
        return DBSession.query(db.exists().where(db.and_(
            Setting.component == component, Setting.name == name
        ))).scalar()

    def settings_get(self, component, name):
        try:
            obj = Setting.filter_by(component=component, name=name).one()
            return json.loads(obj.value)
        except NoResultFound:
            raise KeyError("Setting %s.%s not found!" % (component, name))

    def settings_set(self, component, name, value):
        try:
            obj = Setting.filter_by(component=component, name=name).one()
        except NoResultFound:
            obj = Setting(component=component, name=name).persist()
        obj.value = json.dumps(value)

    def settings_delete(self, component, name):
        try:
            DBSession.delete(Setting.filter_by(
                component=component, name=name).one())
        except NoResultFound:
            pass

    def init_settings(self, component, name, value):
        try:
            self.settings_get(component, name)
        except KeyError:
            self.settings_set(component, name, value)

    def query_stat(self):
        result = dict()
        try:
            result['full_name'] = self.settings_get('core', 'system.full_name')
        except KeyError:
            pass

        result['database_size'] = DBSession.query(db.func.pg_database_size(
            db.func.current_database(),)).scalar()

        return result

    def _engine_url(self, error_on_pwfile=False):
        opt_db = self.options.with_prefix('database')
        kwargs = dict()
        kwargs['host'] = opt_db['host']
        kwargs['database'] = opt_db['name']
        kwargs['username'] = opt_db['user']

        if opt_db['password'] is not None:
            kwargs['password'] = opt_db['password']
        elif opt_db['pwfile'] is not None:
            try:
                with io.open(opt_db['pwfile']) as fd:
                    kwargs['password'] = fd.read().rstrip()
            except FileNotFoundError:
                if error_on_pwfile:
                    raise
        
        return make_engine_url(EngineURL(
            'postgresql+psycopg2', **kwargs))        

    option_annotations = (
        Option('system.name', default="NextGIS Web"),
        Option('system.full_name', default="NextGIS Web"),

        # Database options
        Option('database.host', default="localhost"),
        Option('database.name', default="nextgisweb"),
        Option('database.user', default="nextgisweb"),
        Option('database.password', secure=True, default=None),
        Option('database.pwfile', default=None),
        Option(
            'database.check_at_startup', bool, default=False,
            doc="Check database connection at initialization. So if database is not available "
                "application would not start."),

        # Data storage
        Option(
            'sdir', required=True, doc="Path to filesytem data storage where data stored along "
            "with database. Other components file_upload create subdirectories in it."),

        # Backup storage
        Option(
            'backup.path',
            doc="Path to directory in filesystem where backup created if target destination is "
                "not specified."),
        Option(
            'backup.filename', default='%Y%m%d-%H%M%S.ngwbackup',
            doc="File name template (passed to strftime) for filename in backup.path if backup "
                "target destination is not specified"),

        # Ignore packages and components
        Option('packages.ignore'),
        Option('components.ignore'),
        # Locale settings
        Option('locale.default', default='en'),
        Option('locale.available', list, default=['en', 'ru']),
        # Other deployment settings
        Option('support_url', default="https://nextgis.com/contact/"),
        Option('enable_snippets', bool, default=True),
        # Debug settings
        Option('debug', bool, default=False, doc="Enable additional debug tools."),
    )
