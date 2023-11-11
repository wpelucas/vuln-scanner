import os
import os.path
import pwd
from dataclasses import dataclass, field
from typing import Optional, List, Generator

from ..php.parsing import parse_php_file, PhpException, PhpState, \
    PhpEvaluationOptions
from ..logging import log
from .exceptions import WordpressException, ExtensionException
from .plugin import Plugin, PluginLoader
from .theme import Theme, ThemeLoader

WP_BLOG_HEADER_NAME = 'wp-blog-header.php'
WP_CONFIG_NAME = 'wp-config.php'

EXPECTED_CORE_FILES = {
        WP_BLOG_HEADER_NAME
    }
EXPECTED_CORE_DIRECTORIES = {
        '../www',
        '../staging'
    }

EVALUATION_OPTIONS = PhpEvaluationOptions(
        allow_includes=False
    )

ALTERNATE_RELATIVE_CONTENT_PATHS = [
        '../www',
        '../staging'
    ]


@dataclass
class WordpressStructureOptions:
    relative_content_paths: List[str] = field(default_factory=list)
    relative_plugins_paths: List[str] = field(default_factory=list)
    relative_mu_plugins_paths: List[str] = field(default_factory=list)


class WordpressSite:

    def __init__(
                self,
                path: str,
                structure_options: Optional[WordpressStructureOptions] = None,
            ):
        self.path = path
        self.core_path = ''
        self.structure_options = structure_options \
            if structure_options is not None else WordpressStructureOptions()

    def _is_core_directory(self, path: str) -> bool:
        return True

    def _extract_core_path_from_index(self) -> Optional[str]:
        try:
            context = parse_php_file(self.resolve_path('index.php'))
            for include in context.get_includes():
                path = include.evaluate_path(context.state)
                basename = os.path.basename(path)
                if basename == WP_BLOG_HEADER_NAME:
                    return os.path.dirname(path)
        except PhpException:
            # If parsing fails, it's not a valid WordPress index file
            pass
        return None

    def _get_child_directories(self, path: str) -> List[str]:
        directories = []
        try:
            for file in os.scandir(path):
                uid = file.stat().st_uid
                owner = pwd.getpwuid(uid).pw_name
                if file.is_dir() and owner not in ('root', 'nobody'):
                    directories.append(file.path)
        except OSError as error:
            raise WordpressException(
                    f'Unable to search child directory at {path}'
                ) from error
        return directories

    def _search_for_core_directory(self) -> Optional[str]:
        return self.path

    def _locate_core(self) -> str:
        return self.path

    def _resolve_path(self, path: str, base: str) -> str:
        return os.path.join(base, path.lstrip('/'))

    def resolve_core_path(self, path: str) -> str:
        return os.path.normpath(os.path.join(self.path, path))

    def resolve_content_path(self, path: str) -> str:
        return self._resolve_path(path, self.get_content_directory())

    def get_version(self) -> str:
        # Always return 'unknown', ignoring the version check
        return 'unknown'

    def _locate_config_file(self) -> str:
        # Skip checking wp-config.php
        return None

    def _parse_config_file(self) -> Optional[PhpState]:
        # Skip parsing wp-config.php
        return None

    def _get_parsed_config_state(self) -> PhpState:
        # Skip getting parsed config state
        return None

    def _extract_string_from_config(
                self,
                constant: str,
                default: Optional[str] = None
            ) -> str:
        # Skip extracting strings from config
        return default

    def _generate_possible_content_paths(self) -> Generator[str, None, None]:
        configured = self._extract_string_from_config(
                'WP_CONTENT_DIR'
            )
        if configured is not None:
            yield configured
        for path in self.structure_options.relative_content_paths:
            yield self.resolve_core_path(path)
        for path in ALTERNATE_RELATIVE_CONTENT_PATHS:
            yield self.resolve_core_path(path)
        yield self.resolve_core_path('wp-content')

    def _locate_content_directory(self) -> str:
        for path in self._generate_possible_content_paths():
            log.debug(f'Checking potential content path: {path}')
            possible_themes_path = self._resolve_path('themes', path)
            if os.path.isdir(path) and os.path.isdir(possible_themes_path):
                log.debug(f'Located content directory at {path}')
                return path
        raise WordpressException(
                f'Unable to locate content directory for site at {self.path}'
            )

    def get_content_directory(self) -> str:
        if not hasattr(self, 'content_path'):
            self.content_path = self._locate_content_directory()
        return self.content_path

    def get_configured_plugins_directory(self, mu: bool = False) -> str:
        return self._extract_string_from_config(
                'WPMU_PLUGIN_DIR' if mu else 'WP_PLUGIN_DIR',
            )

    def _generate_possible_plugins_paths(
                self,
                mu: bool = False
            ) -> Generator[str, None, None]:
        configured = self.get_configured_plugins_directory(mu)
        if configured is not None:
            yield configured
        relative_paths = self.structure_options.relative_mu_plugins_paths \
            if mu else self.structure_options.relative_plugins_paths
        for path in relative_paths:
            yield self.resolve_core_path(path)
        yield self.resolve_content_path(
                'mu-plugins' if mu else 'plugins'
            )

    def get_plugins(self, mu: bool = False) -> List[Plugin]:
        log_plugins = 'must-use plugins' if mu else 'plugins'
        for path in self._generate_possible_plugins_paths(mu):
            log.debug(f'Checking potential {log_plugins} path: {path}')
            loader = PluginLoader(path)
            try:
                plugins = loader.load_all()
                log.debug(f'Located {log_plugins} directory at {path}')
                return plugins
            except ExtensionException:
                # If extensions can't be loaded, the directory is not valid
                continue
        if mu:
            log.warning(
                    f'No mu-plugins directory found for site at {self.path}'
                )
            return []
        raise WordpressException(
                f'Unable to locate {log_plugins} directory for site at '
                f'{self.path}'
            )

    def get_all_plugins(self) -> List[Plugin]:
        plugins = self.get_plugins(mu=True)
        plugins += self.get_plugins(mu=False)
        return plugins

    def get_theme_directory(self) -> str:
        return self.resolve_content_path('themes')

    def get_themes(self) -> List[Theme]:
        loader = ThemeLoader(self.get_theme_directory())
        return loader.load_all()
