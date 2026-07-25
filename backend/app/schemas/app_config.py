"""公开的应用配置响应。"""

from pydantic import BaseModel


class AcademicYearDisplay(BaseModel):
    storage: str
    min: int
    max: int
    label_format: str
    term_labels: dict[int, str]


class AppConfigOut(BaseModel):
    school_name: str
    timezone: str
    role_display_names: dict[str, str]
    academic_year: AcademicYearDisplay
