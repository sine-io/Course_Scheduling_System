"""部署配置档公开响应。"""

from pydantic import BaseModel


class AcademicYearDisplay(BaseModel):
    storage: str
    min: int
    max: int
    label_format: str
    term_labels: dict[int, str]


class AppConfigOut(BaseModel):
    profile: str
    school_profile: str
    locale: str
    language: str
    school_name: str
    timezone: str
    tz: str
    role_display_names: dict[str, str]
    roles: dict[str, str]
    terms: dict[str, str]
    academic_year: AcademicYearDisplay
