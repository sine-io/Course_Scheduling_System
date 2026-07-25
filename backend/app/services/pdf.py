"""HTML → PDF(WeasyPrint,M5-0 基础;M5-1 课表导出创建于此)。

WeasyPrint 的系统依赖(Pango/Cairo)与中文内嵌字体只装在 **worker** 镜像;
导出统一走后台任务。故 `weasyprint` 为延迟导入——api 导入本模块不会失败,
只有真正调用 `render_pdf`(在 worker)才需要那些依赖。
"""


def render_pdf(html: str, *, base_url: str | None = None) -> bytes:
    """把 HTML 字符串渲染成 PDF bytes。中文由镜像内嵌的 Noto CJK 字体呈现。"""
    from weasyprint import HTML  # 延迟导入:见模块说明

    return HTML(string=html, base_url=base_url).write_pdf()
