"""模型结构化输出的确定性解析边界。"""

from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from agents.schemas import IssueAnalysis


class AnalysisOutputErrorCode(StrEnum):
    INVALID_OUTPUT_TYPE = "invalid_output_type"
    EMPTY_OUTPUT = "empty_output"
    INVALID_JSON = "invalid_json"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"


class AnalysisOutputError(ValueError):
    """结构化输出无效；对外仅暴露稳定错误码和安全摘要。"""

    def __init__(self, error_code: AnalysisOutputErrorCode, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def parse_issue_analysis(raw_output: Any) -> IssueAnalysis:
    """只接受一个严格符合 ``IssueAnalysis`` 的 JSON 对象。"""

    if not isinstance(raw_output, str):
        raise AnalysisOutputError(
            AnalysisOutputErrorCode.INVALID_OUTPUT_TYPE,
            "模型结构化输出必须是 JSON 字符串。",
        )
    if not raw_output.strip():
        raise AnalysisOutputError(
            AnalysisOutputErrorCode.EMPTY_OUTPUT,
            "模型未返回结构化输出。",
        )

    try:
        return IssueAnalysis.model_validate_json(raw_output, strict=True)
    except ValidationError as exc:
        error_code = (
            AnalysisOutputErrorCode.INVALID_JSON
            if any(error["type"] == "json_invalid" for error in exc.errors())
            else AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED
        )
        message = (
            "模型输出不是合法 JSON。"
            if error_code == AnalysisOutputErrorCode.INVALID_JSON
            else "模型输出不符合 IssueAnalysis 契约。"
        )
        raise AnalysisOutputError(error_code, message) from exc
