from ..subcommands import SubcommandDefinition
from ..config.typing import ConfigDefinitions
from ...api.intelligence import VulnerabilityFeedVariant
from .reporting import VULN_SCAN_REPORT_CONFIG_OPTIONS

config_definitions: ConfigDefinitions = {
    "read-stdin": {
        "description": "Read WordPress base paths from stdin. If not specified"
                       ", paths will automatically be read from stdin when "
                       "input is not from a TTY. Specify --no-read-stdin to "
                       "disable.",
        "context": "ALL",
        "argument_type": "OPTIONAL_FLAG",
        "default": None
    },
    "path-separator": {
        "short_name": "s",
        "description": "Separator used to delimit paths when reading from "
                       "stdin. Defaults to the null byte.",
        "context": "ALL",
        "argument_type": "OPTION",
        "default": "AA==",
        "default_type": "base64"
    },
    "wordpress-path": {
        "short_name": "w",
        "description": "Path to the root of a WordPress installation to scan"
                       " for core vulnerabilities.",
        "context": "CLI",
        "argument_type": "OPTION_REPEATABLE",
        "default": [],
        "meta": {
            "separator": ","
        }
    },
    "plugin-directory": {
        "short_name": "p",
        "description": "Path to a directory containing WordPress plugins to"
                       " scan for vulnerabilities.",
        "context": "CLI",
        "argument_type": "OPTION_REPEATABLE",
        "default": [],
        "meta": {
            "separator": ","
        }
    },
    "theme-directory": {
        "short_name": "t",
        "description": "Path to a directory containing WordPress themes to"
                       " scan for vulnerabilities.",
        "context": "CLI",
        "argument_type": "OPTION_REPEATABLE",
        "default": [],
        "meta": {
            "separator": ","
        }
    },
    **VULN_SCAN_REPORT_CONFIG_OPTIONS,
    "exclude-vulnerability": {
        "short_name": "e",
        "description": "Vulnerability IDs to exclude from scan results.",
        "context": "ALL",
        "argument_type": "OPTION_REPEATABLE",
        "default": [],
        "meta": {
            "separator": ","
        }
    },
    "include-vulnerability": {
        "short_name": "i",
        "description": "Vulnerabilitiy IDs to include in scan results.",
        "context": "ALL",
        "argument_type": "OPTION_REPEATABLE",
        "default": [],
        "meta": {
            "separator": ","
        }
    },
    "informational": {
        "short_name": "I",
        "description": "Whether or not to include informational "
                       "vulnerability records in results.",
        "context": "ALL",
        "argument_type": "FLAG",
        "default": False
    },
    "feed": {
        "short_name": "f",
        "description": "The feed to use for vulnerability information. "
                       "The production feed provides additional details "
                       "that are not included in the scanner feed while "
                       "the scanner feed includes additional vulnerabilities "
                       "that do not yet have sufficient information to be "
                       "included in the production feed.",
        "context": "ALL",
        "argument_type": "OPTION",
        "default": VulnerabilityFeedVariant.SCANNER.path,
        "meta": {
            "valid_options": [
                    variant.path for variant in VulnerabilityFeedVariant
                ]
        }
    }
}

cacheable_types = {
    'wordfence.intel.vulnerabilities.VulnerabilityIndex',
    'wordfence.intel.vulnerabilities.ScannerVulnerability',
    'wordfence.intel.vulnerabilities.ProductionVulnerability',
    'wordfence.intel.vulnerabilities.Software',
    'wordfence.intel.vulnerabilities.ProductionSoftware',
    'wordfence.intel.vulnerabilities.SoftwareType',
    'wordfence.intel.vulnerabilities.VersionRange',
    'wordfence.intel.vulnerabilities.CopyrightInformation',
    'wordfence.intel.vulnerabilities.Copyright',
    'wordfence.intel.vulnerabilities.Cwe',
    'wordfence.intel.vulnerabilities.Cvss'
}

definition = SubcommandDefinition(
    name='vuln-scan',
    description='Scan WordPress installations for vulnerable software',
    config_definitions=config_definitions,
    config_section='VULN_SCAN',
    cacheable_types=cacheable_types
)
