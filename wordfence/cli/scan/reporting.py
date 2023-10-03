from typing import List, IO

from wordfence.scanning.scanner import ScanResult
from wordfence.intel.signatures import SignatureSet, Signature

from ..reporting import Report, ReportFormat, get_config_options, \
        ReportFormatEnum, ReportColumnEnum, ReportRecord, ReportWriter, \
        ReportManager, ReportColumn, \
        REPORT_FORMAT_CSV, REPORT_FORMAT_TSV, REPORT_FORMAT_NULL_DELIMITED, \
        REPORT_FORMAT_LINE_DELIMITED
from ..config import Config
from .progress import ProgressDisplay


class ScanReportColumn(ReportColumnEnum):
    FILENAME = 'filename', lambda record: record.result.path
    SIGNATURE_ID = 'signature_id', lambda record: record.signature.identifier
    SIGNATURE_NAME = 'signature_name', lambda record: record.signature.name
    SIGNATURE_DESCRIPTION = 'signature_description', \
        lambda record: record.signature.description
    MATCHED_TEXT = 'matched_text', lambda record: record.match


class HumanReadableWriter(ReportWriter):

    def __init__(self, target: IO, columns: List[ScanReportColumn]):
        super().__init__(target)
        self._columns = columns

    def _get_value(data: List[str], column: str) -> str:
        return

    def _map_data_to_dict(self, data: List[str]) -> dict:
        return {
            column.header: data[index] for index, column
            in enumerate(self._columns)
        }

    def write_row(self, data: List[str]) -> None:
        values = self._map_data_to_dict(data)
        file = None
        signature_id = None
        if 'filename' in values:
            file = values['filename']
        if 'signature_id' in values:
            signature_id = values['signature_id']
        # TODO: Add more custom messages if desired
        if file is not None:
            if signature_id is not None:
                self._target.write(
                        f"File at {file} matched signature {signature_id}"
                    )
            else:
                self._target.write(
                        f"File {file} matched a signature"
                    )
        else:
            self._target.write(
                    "Match found: " + str(values)
                )
        self._target.write("\n")

    def allows_headers(self) -> bool:
        return False


REPORT_FORMAT_HUMAN = ReportFormat(
        'human',
        lambda stream, columns: HumanReadableWriter(stream, columns)
    )


class ScanReportFormat(ReportFormatEnum):
    CSV = REPORT_FORMAT_CSV
    TSV = REPORT_FORMAT_TSV
    NULL_DELIMITED = REPORT_FORMAT_NULL_DELIMITED
    LINE_DELIMITED = REPORT_FORMAT_LINE_DELIMITED
    HUMAN = REPORT_FORMAT_HUMAN


class ScanReportRecord(ReportRecord):

    def __init__(
                self,
                result: ScanResult,
                signature: Signature,
                match: str
            ):
        self.result = result
        self.signature = signature
        self.match = match


class ScanReport(Report):

    def __init__(
                self,
                format: ScanReportFormat,
                columns: List[ScanReportColumn],
                signature_set: SignatureSet,
                write_headers: bool = False
            ):
        super().__init__(
                format=format,
                columns=columns,
                write_headers=write_headers
            )
        self.signature_set = signature_set

    def add_result(self, result: ScanResult) -> None:
        records = []
        for signature_id, match in result.matches.items():
            signature = self.signature_set.get_signature(signature_id)
            record = ScanReportRecord(
                    result=result,
                    signature=signature,
                    match=match
                )
            records.append(record)
        self.write_records(records)


SCAN_REPORT_CONFIG_OPTIONS = get_config_options(
        ScanReportFormat,
        ScanReportColumn,
        [ScanReportColumn.FILENAME]
    )


class ScanReportManager(ReportManager):

    def __init__(
                self,
                config: Config,
                signature_set: SignatureSet
            ):
        super().__init__(
                formats=ScanReportFormat,
                columns=ScanReportColumn,
                config=config,
                read_stdin=config.read_stdin,
                input_delimiter=config.file_list_separator
            )
        self.signature_set = signature_set
        self.progress = None

    def set_progress_display(self, progress: ProgressDisplay) -> None:
        self.progress = progress

    def _instantiate_report(
                self,
                format: ReportFormat,
                columns: List[ReportColumn],
                write_headers: bool
            ) -> ScanReport:
        return ScanReport(
                format,
                columns,
                self.signature_set,
                write_headers
            )

    def _get_stdout_target(self) -> IO:
        if self.progress is not None:
            return self.progress.get_output_stream()
        return super()._get_stdout_target()
