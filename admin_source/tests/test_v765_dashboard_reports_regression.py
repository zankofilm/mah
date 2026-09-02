import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _Label:
    def __init__(self):
        self.text = None

    def setText(self, value):
        self.text = value


class _Database:
    def get_generated_documents(self, limit=5000):
        assert limit == 5000
        return [
            {"title": "گزارش مالی محله"},
            {"template_name": "گزارش پروژه عمرانی"},
            {"title": "خدمات شهری و پسماند"},
            {"title": "گزارش جمعیتی خانوار"},
        ]


def _load_method():
    source = (ROOT / "dashboard_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_fill_reports_table"
    )
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    namespace = {
        "_fa_number": lambda value: str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")),
    }
    exec(compile(module, "dashboard_window.py", "exec"), namespace)
    return source, method, namespace["_fill_reports_table"]


def test_dashboard_report_refresh_runs_without_removed_reports_table():
    source, method, fill_reports = _load_method()
    dashboard = type("DashboardStub", (), {})()
    dashboard.db = _Database()
    dashboard.report_summary_value_labels = [_Label() for _ in range(4)]

    fill_reports(dashboard)

    assert [label.text for label in dashboard.report_summary_value_labels] == ["۱", "۱", "۱", "۱"]
    direct_accesses = [
        node for node in ast.walk(method)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "reports_table"
    ]
    assert not direct_accesses
    assert 'getattr(self, "reports_table", None)' in source
