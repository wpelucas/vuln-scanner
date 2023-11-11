from typing import Dict, List, Set
from uuid import UUID

from ...intel.vulnerabilities import VulnerabilityIndex, Vulnerability, \
        VulnerabilityScanner, VulnerabilityFilter, is_cve_id
from ...api.intelligence import VulnerabilityFeedVariant
from ...util.caching import Cacheable, DURATION_ONE_DAY
from ...wordpress.site import WordpressSite, WordpressStructureOptions
from ...wordpress.plugin import PluginLoader, Plugin
from ...wordpress.theme import ThemeLoader, Theme
from ...logging import log
from ..subcommands import Subcommand
from .reporting import VulnScanReportManager
from .exceptions import VulnScanningConfigurationException


class VulnScanSubcommand(Subcommand):

    def _load_vulnerability_index(
                self,
                variant: VulnerabilityFeedVariant
            ) -> VulnerabilityIndex:
        def initialize_vulnerability_index() -> VulnerabilityIndex:
            client = self.context.get_wfi_client()
            vulnerabilities = client.fetch_vulnerability_feed(variant)
            return VulnerabilityIndex(vulnerabilities)
        vulnerability_index = Cacheable(
                f'vulnerability_index_{variant.path}',
                initialize_vulnerability_index,
                DURATION_ONE_DAY
            )
        return vulnerability_index.get(self.cache)

    def _scan_plugins(
                self,
                plugins: List[Plugin],
                scanner: VulnerabilityScanner
            ) -> Dict[str, Vulnerability]:
        for plugin in plugins:
            log.debug(f'Plugin {plugin.slug}, version: {plugin.version}')
            scanner.scan_plugin(plugin)

    def _scan_plugin_directory(
                self,
                directory: str,
                scanner: VulnerabilityScanner
            ) -> Dict[str, Vulnerability]:
        loader = PluginLoader(directory)
        plugins = loader.load_all()
        return self._scan_plugins(plugins, scanner)

    def _scan_themes(
                self,
                themes: List[Theme],
                scanner: VulnerabilityScanner
            ) -> Dict[str, Vulnerability]:
        for theme in themes:
            log.debug(f'Theme {theme.slug}, version: {theme.version}')
            scanner.scan_theme(theme)

    def _scan_theme_directory(
                self,
                directory: str,
                scanner: VulnerabilityScanner
            ) -> Dict[str, Vulnerability]:
        loader = ThemeLoader(directory)
        themes = loader.load_all()
        return self._scan_themes(themes, scanner)

    def _scan(
                self,
                path: str,
                scanner: VulnerabilityScanner,
                check_extensions: bool = False,
                structure_options: WordpressStructureOptions = None
            ) -> Dict[str, Vulnerability]:
        site = WordpressSite(
                path=path,
                structure_options=structure_options
            )
        #log.debug(f'Located WordPress files at {site.core_path}')
        version = site.get_version()
        log.debug(f'WordPress Core Version: {version}')
        #scanner.scan_core(version)
        if check_extensions:
            self._scan_plugins(site.get_all_plugins(), scanner)
            self._scan_themes(site.get_themes(), scanner)

    def _get_vulnerability_label(self, count: int) -> str:
        if count == 1:
            return 'vulnerability'
        else:
            return 'vulnerabilities'

    def _output_summary(self, scanner: VulnerabilityScanner) -> None:
        unique_count = scanner.get_vulnerability_count()
        total_count = scanner.get_total_count()
        unique_label = self._get_vulnerability_label(unique_count)
        total_label = self._get_vulnerability_label(total_count)
        # log.info(
        #         f'Found {unique_count} unique {unique_label} / {total_count} '
        #         f'total {total_label}'
        #     )

    def _validate_vulnerability_ids(
                self,
                identifiers: List[str],
                feed_variant: VulnerabilityFeedVariant) -> Set[str]:
        valid = set()
        for identifier in identifiers:
            if is_cve_id(identifier):
                if feed_variant is not VulnerabilityFeedVariant.PRODUCTION:
                    raise Exception(
                            'CVE IDs can only be used to filter '
                            'vulnerabilities with the production feed'
                        )
                valid.add(identifier)
            else:
                try:
                    uuid = UUID(identifier)
                    valid.add(str(uuid))
                except ValueError:
                    raise Exception(
                            f'Malformed vulnerability ID: {identifier}'
                        )
        return valid

    def _initialize_filter(
                self,
                feed_variant: VulnerabilityFeedVariant
            ) -> VulnerabilityFilter:
        excluded = self._validate_vulnerability_ids(
                self.config.exclude_vulnerability,
                feed_variant
            )
        included = self._validate_vulnerability_ids(
                self.config.include_vulnerability,
                feed_variant
            )
        return VulnerabilityFilter(
                excluded=excluded,
                included=included,
                informational=self.config.informational
            )

    def _scan_site(
                self,
                path: str,
                scanner: VulnerabilityScanner,
                structure_options: WordpressStructureOptions = None
            ) -> None:
        #log.info(f'Scanning site at {path}...')
        self._scan(
                path,
                scanner,
                check_extensions=True,
                structure_options=structure_options
            )

    def _requires_paths(self) -> bool:
        required = self.config.require_path
        return (
                required is True or
                (required is None and self.context.has_terminal_input)
            )

    def _check_required_paths(self) -> bool:
        if not self._requires_paths():
            return True
        return (len(self.config.trailing_arguments) +
                len(self.config.wordpress_path) +
                len(self.config.plugin_directory) +
                len(self.config.theme_directory)) > 0

    def _raise_path_error(self) -> None:
        raise VulnScanningConfigurationException(
                'At least one WordPress path must be specified'
            )

    def invoke(self) -> int:
        feed_variant = VulnerabilityFeedVariant.for_path(self.config.feed)
        report_manager = VulnScanReportManager(self.config, feed_variant)
        io_manager = report_manager.get_io_manager()
        if not io_manager.should_read_stdin() and \
                not self._check_required_paths():
            self._raise_path_error()
        if self.config.output_format == 'human' \
                and not self.context.allows_color:
            log.warning(
                    'The human output format requires a terminal with color '
                    'support to function properly. See --output-format for '
                    'other options.'
                )
        vulnerability_index = self._load_vulnerability_index(feed_variant)
        vulnerability_filter = self._initialize_filter(feed_variant)
        for invalid_id in vulnerability_filter.get_invalid_ids(
                    vulnerability_index
                ):
            log.warning(
                    f'Unrecognized vulnerability identifier: {invalid_id}, '
                    'expected a valid UUID or CVE ID'
                )
        scanner = VulnerabilityScanner(
                vulnerability_index,
                self._initialize_filter(feed_variant)
            )
        structure_options = WordpressStructureOptions(
                relative_content_paths=self.config.relative_content_path,
                relative_plugins_paths=self.config.relative_plugins_path,
                relative_mu_plugins_paths=self.config.relative_mu_plugins_path
            )
        with report_manager.open_output_file() as output_file:
            report = report_manager.initialize_report(output_file)
            scanner.register_result_callback(report.add_result)
            for path in self.config.trailing_arguments:
                self._scan_site(
                        path,
                        scanner,
                        structure_options=structure_options
                    )
            if io_manager.should_read_stdin():
                reader = io_manager.get_input_reader()
                path_count = 0
                for path in reader.read_all_entries():
                    self._scan_site(
                            path,
                            scanner,
                            structure_options=structure_options
                        )
                    path_count += 1
                if self._requires_paths() and path_count == 0:
                    self._raise_path_error()
            for path in self.config.wordpress_path:
    # log.info(f'Scanning core installation at {path}...')
                self._scan(
                    path,
                    scanner,
                    structure_options=structure_options
                )
            for path in self.config.plugin_directory:
                # log.info(f'Scanning plugin directory at {path}...')
                self._scan_plugin_directory(path, scanner)
            for path in self.config.theme_directory:
                # log.info(f'Scanning theme directory at {path}...')
                self._scan_theme_directory(path, scanner)
            self._output_summary(scanner)
        return 0


factory = VulnScanSubcommand