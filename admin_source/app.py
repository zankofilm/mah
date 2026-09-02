# -*- coding: utf-8 -*-
"""
نقطه ورود اصلی برنامه.
جریان برنامه:
  1) پنجره ورود (Login) نمایش داده می‌شود.
  2) با ورود موفق، داشبورد اصلی باز می‌شود.
  3) از داشبورد، کاربر می‌تواند وارد یکی از ماژول‌ها شود:
       - بلوک‌بندی و منطقه‌بندی (MainWindow از main.py)
       - اعضای شورای محلات (CouncilModuleWindow از council_module.py)
       - اولویت‌بندی مشکلات و درخواست‌ها (PriorityRequestsWindow)
       - اقدامات انجام‌شده (CompletedActionsWindow)
       - گزارش‌گیری (ReportsModuleWindow)
       - تنظیمات سیستم و حساب کاربری: بکاپ/ریست/تغییر رمز/هدر سفارشی (SystemSettingsWindow)
  4) از هر ماژول می‌توان به داشبورد بازگشت.

یک اتصال واحد به دیتابیس (Database) در کل عمر برنامه استفاده می‌شود و
بین تمام پنجره‌ها به اشتراک گذاشته می‌شود.
"""

import sys
import threading
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from database import Database
from theme import MAIN_STYLESHEET
from login_window import LoginWindow
from dashboard_window import DashboardWindow
from settings_window import SystemSettingsWindow
from main import MainWindow
from council_module import CouncilModuleWindow
from committees_module import NeighborhoodCommitteesWindow
from social_council_module import SocialCouncilWindow
from priority_module import PriorityRequestsWindow, CompletedActionsWindow
from reports_module import ReportsModuleWindow
from city_wide_map_module import CityWideMapWindow
from neighborhood_management import NeighborhoodManagementWindow
from city_comparison_module import CityComparisonWindow
from correspondence_module import CorrespondenceWindow
from approval_templates_module import ApprovalTemplatesWindow
from management_calendar_module import ManagementCalendarWindow
from project_control_module import ProjectControlWindow
from contracts_satisfaction_module import ContractsSatisfactionWindow
from data_governance_module import DataGovernanceWindow
from production_center import ProductionCenterWindow
from operations_center import OperationsCenterWindow
from client_management_module import ClientManagementWindow
from messaging_module import MessagingWindow
from population_estimation_module import PopulationEstimationWindow
from production_health import RuntimeSessionGuard, cleanup_runtime_files
from runtime_paths import migrate_legacy_runtime_data, get_data_dir
from asset_manager import ensure_leaflet_assets
from tile_server import start_tile_server, stop_tile_server, update_tile_server_database
from version import APP_NAME, APP_VERSION
from windows_platform import configure_windows_process
from logging_setup import configure_logging, install_exception_hook
from icon_manager import polish_widget_tree, get_icon, UiPolishFilter
from ui_typography import apply_application_typography
from responsive_ui import ResponsiveUiFilter
from access_control import has_permission
from jalali_widgets import JalaliDisplayFilter


class AppController:
    """
    مدیریت مرکزی جریان بین پنجره‌های برنامه.
    به‌جای استفاده از QStackedWidget (که برای پنجره‌های سنگین/جداگانه پیچیده می‌شود)،
    هر پنجره را به‌صورت جداگانه نمایش/مخفی می‌کند و رفت‌وآمد بین آن‌ها را مدیریت می‌کند.
    """

    def __init__(self, session_guard=None, previous_unclean=False):
        self.session_guard = session_guard
        self.previous_unclean = previous_unclean
        self._unclean_warning_shown = False
        self.db = Database()
        self.current_user = None
        try:
            self.db.ensure_daily_backup(keep=14)
        except Exception:
            pass
        try:
            self.tile_server = start_tile_server(self.db)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("tile server startup failed: %s", exc)
            self.tile_server = None
        # دارایی‌های Leaflet در پس‌زمینه آماده می‌شوند تا راه‌اندازی برنامه معطل شبکه نماند.
        threading.Thread(target=ensure_leaflet_assets, daemon=True, name="LeafletAssetBootstrap").start()

        self.login_window = LoginWindow(self.db)
        polish_widget_tree(self.login_window)
        self.login_window.login_successful.connect(self.show_dashboard)

        self.dashboard_window = None
        self.blocking_window = None
        self.council_window = None
        self.committees_window = None
        self.social_council_window = None
        self.priority_window = None
        self.actions_window = None
        self.reports_window = None
        self.system_settings_window = None
        self.city_wide_map_window = None
        self.neighborhood_management_window = None
        self.city_comparison_window = None
        self.correspondence_window = None
        self.approval_templates_window = None
        self.management_calendar_window = None
        self.project_control_window = None
        self.contracts_satisfaction_window = None
        self.data_governance_window = None
        self.production_center_window = None
        self.operations_center_window = None
        self.client_management_window = None
        self.messaging_window = None
        self.population_estimation_window = None

        self.login_window.show()

    def _show_primary_window(self, window):
        """تمام صفحات اصلی سامانه را با اندازه و حالت یکسان نمایش می‌دهد."""
        if window is None:
            return
        # صفحات اصلی همیشه Maximized باز می‌شوند؛ پنجره‌های محاوره‌ای و فرم‌های کوچک مستثنا هستند.
        window.showMaximized()
        window.raise_()
        window.activateWindow()

    # ---------------- داشبورد ----------------
    def show_dashboard(self, user=None):
        self.login_window.close()
        if user is not None:
            self.current_user = dict(user)
            self.db.set_current_user(self.current_user)
            if self.dashboard_window is not None:
                self.dashboard_window.deleteLater()
                self.dashboard_window = None

        if self.dashboard_window is None:
            self.dashboard_window = DashboardWindow(self.db, self.current_user)
            polish_widget_tree(self.dashboard_window)
            self.dashboard_window.open_blocking_module.connect(self.show_blocking_module)
            self.dashboard_window.open_council_module.connect(self.show_council_module)
            self.dashboard_window.open_committees_module.connect(self.show_committees_module)
            self.dashboard_window.open_social_council_module.connect(self.show_social_council_module)
            self.dashboard_window.open_priority_module.connect(self.show_priority_module)
            self.dashboard_window.open_actions_module.connect(self.show_actions_module)
            self.dashboard_window.open_settings_module.connect(lambda: self.show_system_settings_module(False))
            self.dashboard_window.open_reports_module.connect(self.show_reports_module)
            self.dashboard_window.open_system_settings_module.connect(lambda: self.show_system_settings_module(True))
            self.dashboard_window.open_ai_settings_module.connect(
                lambda: self.show_system_settings_module(True, initial_tab="هوش مصنوعی")
            )
            self.dashboard_window.open_city_wide_map_module.connect(self.show_city_wide_map_module)
            self.dashboard_window.open_neighborhood_management_module.connect(self.show_neighborhood_management_module)
            self.dashboard_window.open_city_comparison_module.connect(self.show_city_comparison_module)
            self.dashboard_window.open_correspondence_module.connect(self.show_correspondence_module)
            self.dashboard_window.open_approval_templates_module.connect(self.show_approval_templates_module)
            self.dashboard_window.open_management_calendar_module.connect(self.show_management_calendar_module)
            self.dashboard_window.open_project_control_module.connect(self.show_project_control_module)
            self.dashboard_window.open_contracts_satisfaction_module.connect(self.show_contracts_satisfaction_module)
            self.dashboard_window.open_data_governance_module.connect(self.show_data_governance_module)
            self.dashboard_window.open_production_center_module.connect(self.show_production_center_module)
            self.dashboard_window.open_operations_center_module.connect(self.show_operations_center_module)
            self.dashboard_window.open_client_management_module.connect(self.show_client_management_module)
            self.dashboard_window.open_messaging_module.connect(self.show_messaging_module)
            self.dashboard_window.open_population_estimation_module.connect(self.show_population_estimation_module)
            self.dashboard_window.search_result_activated.connect(self.open_search_result)
            self.dashboard_window.logout_requested.connect(self.logout)

        self.dashboard_window.refresh_stats()
        self._show_primary_window(self.dashboard_window)
        if self.previous_unclean and not self._unclean_warning_shown:
            self._unclean_warning_shown = True
            QMessageBox.warning(
                self.dashboard_window, "بسته‌شدن غیرعادی",
                "برنامه در اجرای قبلی به‌صورت عادی بسته نشده است. برای اطمینان، از «مرکز سلامت سامانه» کنترل سلامت و آزمون بازیابی را اجرا کنید."
            )

    def _require_permission(self, permission):
        role = (self.current_user or {}).get("role")
        if has_permission(role, permission):
            return True
        QMessageBox.warning(None, "عدم دسترسی", "حساب کاربری فعلی مجوز انجام این عملیات را ندارد.")
        return False

    def open_search_result(self, result):
        entity_type = (result or {}).get("entity_type")
        spatial_types = {"zone", "street", "place", "mosque"}
        management_types = {"issue", "action", "citizen_request", "council_member", "agency"}
        committee_types = {"committee", "committee_member"}
        social_types = {"social_council_member", "social_issue", "social_meeting", "social_resolution", "social_action_plan"}
        role = (self.current_user or {}).get("role")
        if entity_type in social_types and has_permission(role, "council"):
            self.show_social_council_module()
        elif entity_type in committee_types and has_permission(role, "council"):
            self.show_committees_module()
        elif entity_type in {"governance_record", "sync_conflict", "publication"} and has_permission(role, "governance"):
            self.show_data_governance_module()
        elif entity_type in {"contract", "contractor", "satisfaction_survey", "community_participation"} and has_permission(role, "contracts"):
            self.show_contracts_satisfaction_module()
        elif entity_type in {"annual_program", "project", "project_milestone", "project_indicator", "project_risk", "project_change"} and has_permission(role, "project_control"):
            self.show_project_control_module()
        elif entity_type == "calendar_event" and has_permission(role, "monitoring"):
            self.show_management_calendar_module()
        elif entity_type in {"approval", "generated_document", "document_template"} and has_permission(role, "approvals"):
            self.show_approval_templates_module()
        elif entity_type == "letter" and has_permission(role, "correspondence"):
            self.show_correspondence_module()
        elif entity_type == "execution_case" and has_permission(role, "operations_center"):
            self.show_operations_center_module()
        elif entity_type in spatial_types and has_permission(role, "blocking"):
            self.show_blocking_module()
        elif entity_type in management_types and has_permission(role, "neighborhood"):
            self.show_neighborhood_management_module()
        elif has_permission(role, "reports"):
            self.show_reports_module()
        else:
            QMessageBox.information(None, "نتیجه جستجو", "نتیجه پیدا شد، اما حساب فعلی مجوز بازکردن ماژول مرتبط را ندارد.")

    # ---------------- کمیته‌های شش‌گانه محله‌محور ----------------
    def show_committees_module(self):
        if not self._require_permission("council"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.committees_window is None:
            self.committees_window = NeighborhoodCommitteesWindow(self.db)
            polish_widget_tree(self.committees_window)
            self.committees_window.back_requested.connect(self.back_from_committees_module)
        else:
            self.committees_window.refresh_zones()
        self._show_primary_window(self.committees_window)

    def back_from_committees_module(self):
        if self.committees_window:
            self.committees_window.hide()
        self.show_dashboard()

    # ---------------- شورای اجتماعی مستقل ----------------
    def show_social_council_module(self):
        if not self._require_permission("council"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.social_council_window is None:
            self.social_council_window = SocialCouncilWindow(self.db)
            polish_widget_tree(self.social_council_window)
            self.social_council_window.back_requested.connect(self.back_from_social_council_module)
        else:
            self.social_council_window.refresh_zones()
        self._show_primary_window(self.social_council_window)

    def back_from_social_council_module(self):
        if self.social_council_window:
            self.social_council_window.hide()
        self.show_dashboard()

    # ---------------- مدیریت کلاینت‌های آفلاین ----------------
    def show_client_management_module(self):
        if not self._require_permission("client_management"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.client_management_window is None:
            self.client_management_window = ClientManagementWindow(self.db)
            polish_widget_tree(self.client_management_window)
            self.client_management_window.back_requested.connect(self.back_from_client_management_module)
        else:
            self.client_management_window.refresh_all()
        self._show_primary_window(self.client_management_window)

    def back_from_client_management_module(self):
        if self.client_management_window:
            self.client_management_window.hide()
        self.show_dashboard()

    # ---------------- ارسال پیام به اعضای بلوک‌ها ----------------
    def show_messaging_module(self):
        if not self._require_permission("messaging"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.messaging_window is None:
            self.messaging_window = MessagingWindow(self.db, self.current_user)
            polish_widget_tree(self.messaging_window)
            self.messaging_window.back_requested.connect(self.back_from_messaging_module)
        self._show_primary_window(self.messaging_window)

    def back_from_messaging_module(self):
        if self.messaging_window:
            self.messaging_window.hide()
        self.show_dashboard()

    # ---------------- برآورد جمعیت بلوک‌ها ----------------
    def show_population_estimation_module(self):
        if not self._require_permission("population"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.population_estimation_window is None:
            self.population_estimation_window = PopulationEstimationWindow(self.db, self.current_user)
            polish_widget_tree(self.population_estimation_window)
            self.population_estimation_window.back_requested.connect(self.back_from_population_estimation_module)
        else:
            self.population_estimation_window.refresh_all()
        self._show_primary_window(self.population_estimation_window)

    def back_from_population_estimation_module(self):
        if self.population_estimation_window:
            self.population_estimation_window.hide()
        self.show_dashboard()

    # ---------------- مرکز سلامت و بازیابی ----------------
    def show_production_center_module(self):
        if not self._require_permission("system_settings"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.operations_center_window:
            self.operations_center_window.hide()
        if self.production_center_window is None:
            self.production_center_window = ProductionCenterWindow(self.db, self.previous_unclean)
            polish_widget_tree(self.production_center_window)
            self.production_center_window.back_requested.connect(self.back_from_production_center_module)
        else:
            self.production_center_window.refresh_health()
        self._show_primary_window(self.production_center_window)

    def back_from_production_center_module(self):
        if self.production_center_window:
            self.production_center_window.hide()
        self.show_dashboard()

    # ---------------- حکمرانی داده و حل تعارض ----------------
    def show_data_governance_module(self):
        if not self._require_permission("governance"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.data_governance_window is None:
            self.data_governance_window = DataGovernanceWindow(self.db)
            polish_widget_tree(self.data_governance_window)
            self.data_governance_window.back_requested.connect(self.back_from_data_governance_module)
        else:
            self.data_governance_window.refresh_all()
        self._show_primary_window(self.data_governance_window)

    def back_from_data_governance_module(self):
        if self.data_governance_window:
            self.data_governance_window.hide()
        self.show_dashboard()

    # ---------------- قراردادها، پیمانکاران و رضایت مردمی ----------------
    def show_contracts_satisfaction_module(self):
        if not self._require_permission("contracts"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.contracts_satisfaction_window is None:
            self.contracts_satisfaction_window = ContractsSatisfactionWindow(self.db)
            polish_widget_tree(self.contracts_satisfaction_window)
            self.contracts_satisfaction_window.back_requested.connect(self.back_from_contracts_satisfaction_module)
        else:
            self.contracts_satisfaction_window.refresh_all()
        self._show_primary_window(self.contracts_satisfaction_window)

    def back_from_contracts_satisfaction_module(self):
        if self.contracts_satisfaction_window:
            self.contracts_satisfaction_window.hide()
        self.show_dashboard()

    # ---------------- برنامه عملیاتی و کنترل پروژه ----------------
    def show_project_control_module(self):
        if not self._require_permission("project_control"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.project_control_window is None:
            self.project_control_window = ProjectControlWindow(self.db)
            polish_widget_tree(self.project_control_window)
            self.project_control_window.back_requested.connect(self.back_from_project_control_module)
        else:
            self.project_control_window.refresh_all()
        self._show_primary_window(self.project_control_window)

    def back_from_project_control_module(self):
        if self.project_control_window:
            self.project_control_window.hide()
        self.show_dashboard()

    # ---------------- تقویم مدیریتی و پایش اجرایی ----------------
    def show_management_calendar_module(self):
        if not self._require_permission("monitoring"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.management_calendar_window is None:
            self.management_calendar_window = ManagementCalendarWindow(self.db)
            polish_widget_tree(self.management_calendar_window)
            self.management_calendar_window.back_requested.connect(self.back_from_management_calendar_module)
        else:
            self.management_calendar_window.refresh_all()
        self._show_primary_window(self.management_calendar_window)

    def back_from_management_calendar_module(self):
        if self.management_calendar_window:
            self.management_calendar_window.hide()
        self.show_dashboard()

    # ---------------- گردش تأیید و قالب‌های اداری ----------------
    def show_approval_templates_module(self):
        if not self._require_permission("approvals"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.approval_templates_window is None:
            self.approval_templates_window = ApprovalTemplatesWindow(self.db)
            polish_widget_tree(self.approval_templates_window)
            self.approval_templates_window.back_requested.connect(self.back_from_approval_templates_module)
        else:
            self.approval_templates_window.refresh()
        self._show_primary_window(self.approval_templates_window)

    def back_from_approval_templates_module(self):
        if self.approval_templates_window:
            self.approval_templates_window.hide()
        self.show_dashboard()

    # ---------------- مکاتبات اداری ----------------
    def show_correspondence_module(self):
        if not self._require_permission("correspondence"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.correspondence_window is None:
            self.correspondence_window = CorrespondenceWindow(self.db)
            polish_widget_tree(self.correspondence_window)
            self.correspondence_window.back_requested.connect(self.back_from_correspondence_module)
        else:
            self.correspondence_window.refresh()
        self._show_primary_window(self.correspondence_window)

    def back_from_correspondence_module(self):
        if self.correspondence_window:
            self.correspondence_window.hide()
        self.show_dashboard()

    # ---------------- هسته مدیریت محله‌محور ----------------
    def show_neighborhood_management_module(self):
        if not self._require_permission("neighborhood"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.neighborhood_management_window is None:
            self.neighborhood_management_window = NeighborhoodManagementWindow(self.db)
            polish_widget_tree(self.neighborhood_management_window)
            self.neighborhood_management_window.back_requested.connect(self.back_from_neighborhood_management_module)
        else:
            self.neighborhood_management_window.refresh_zone_list()
        self._show_primary_window(self.neighborhood_management_window)

    def back_from_neighborhood_management_module(self):
        if self.neighborhood_management_window:
            self.neighborhood_management_window.hide()
        self.show_dashboard()

    # ---------------- مقایسه و رتبه‌بندی بلوک‌های شهر ----------------
    def show_city_comparison_module(self):
        if not self._require_permission("neighborhood"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.city_comparison_window is None:
            self.city_comparison_window = CityComparisonWindow(self.db, self.current_user)
            polish_widget_tree(self.city_comparison_window)
            self.city_comparison_window.back_requested.connect(self.back_from_city_comparison_module)
            self.city_comparison_window.open_zone_requested.connect(self._open_zone_from_comparison)
        else:
            self.city_comparison_window.refresh()
        self._show_primary_window(self.city_comparison_window)

    def back_from_city_comparison_module(self):
        if self.city_comparison_window:
            self.city_comparison_window.hide()
        self.show_dashboard()

    def _open_zone_from_comparison(self, zone_id):
        """ورود مستقیم به پرونده جامع یک بلوک، از طریق دوبار کلیک در پنجره مقایسه."""
        if not self._require_permission("neighborhood"):
            return
        if self.city_comparison_window:
            self.city_comparison_window.hide()
        if self.neighborhood_management_window is None:
            self.neighborhood_management_window = NeighborhoodManagementWindow(self.db)
            polish_widget_tree(self.neighborhood_management_window)
            self.neighborhood_management_window.back_requested.connect(self.back_from_neighborhood_management_module)
        self.neighborhood_management_window.open_zone(zone_id)
        self._show_primary_window(self.neighborhood_management_window)

    # ---------------- ماژول بلوک‌بندی ----------------
    def show_blocking_module(self):
        if not self._require_permission("blocking"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.blocking_window is None:
            self.blocking_window = MainWindow(self.db)
            polish_widget_tree(self.blocking_window)
            self.blocking_window.back_to_dashboard.connect(self.back_from_blocking_module)

        self._show_primary_window(self.blocking_window)

    def back_from_blocking_module(self):
        if self.blocking_window:
            self.blocking_window.hide()
        self.show_dashboard()

    # ---------------- ماژول اعضای شورای محلات ----------------
    def show_council_module(self):
        if not self._require_permission("council"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.council_window is None:
            self.council_window = CouncilModuleWindow(self.db)
            polish_widget_tree(self.council_window)
            self.council_window.back_requested.connect(self.back_from_council_module)
        else:
            # بازخوانی لیست مناطق در صورتی که در ماژول بلوک‌بندی تغییری داده شده باشد
            self.council_window.refresh_zone_list()

        self._show_primary_window(self.council_window)
        if hasattr(self.council_window, "focus_member_registration"):
            self.council_window.focus_member_registration()

    def back_from_council_module(self):
        if self.council_window:
            self.council_window.hide()
        self.show_dashboard()

    # ---------------- ماژول اولویت‌بندی مشکلات و درخواست‌ها ----------------
    def show_priority_module(self):
        if not self._require_permission("priority"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.priority_window is None:
            self.priority_window = PriorityRequestsWindow(self.db)
            polish_widget_tree(self.priority_window)
            self.priority_window.back_requested.connect(self.back_from_priority_module)
        else:
            self.priority_window.refresh_zone_list()

        self._show_primary_window(self.priority_window)

    def back_from_priority_module(self):
        if self.priority_window:
            self.priority_window.hide()
        self.show_dashboard()

    # ---------------- ماژول اقدامات انجام‌شده ----------------
    def show_actions_module(self):
        if not self._require_permission("actions"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.actions_window is None:
            self.actions_window = CompletedActionsWindow(self.db)
            polish_widget_tree(self.actions_window)
            self.actions_window.back_requested.connect(self.back_from_actions_module)
        else:
            self.actions_window.refresh_zone_list()

        self._show_primary_window(self.actions_window)

    def back_from_actions_module(self):
        if self.actions_window:
            self.actions_window.hide()
        self.show_dashboard()

    # ---------------- گزارش‌گیری ----------------
    def show_reports_module(self):
        if not self._require_permission("reports"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.reports_window is None:
            self.reports_window = ReportsModuleWindow(self.db)
            polish_widget_tree(self.reports_window)
            self.reports_window.back_requested.connect(self.back_from_reports_module)
        else:
            self.reports_window.refresh()

        self._show_primary_window(self.reports_window)

    def back_from_reports_module(self):
        if self.reports_window:
            self.reports_window.hide()
        self.show_dashboard()

    # ---------------- تنظیمات سیستم (بکاپ/ریست/رمز/هدر) ----------------
    def show_system_settings_module(self, require_admin=False, initial_tab=None):
        permission = "system_settings" if require_admin else "account"
        if not self._require_permission(permission):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.system_settings_window is None:
            self.system_settings_window = SystemSettingsWindow(self.db, self.current_user, initial_tab=initial_tab)
            polish_widget_tree(self.system_settings_window)
            self.system_settings_window.back_requested.connect(self.back_from_system_settings_module)
            self.system_settings_window.restart_required.connect(self.restart_application)
        elif initial_tab:
            self.system_settings_window._jump_to_tab(initial_tab)

        self._show_primary_window(self.system_settings_window)

    def back_from_system_settings_module(self):
        if self.system_settings_window:
            self.system_settings_window.hide()
        self.show_dashboard()

    # ---------------- نقشه کامل شهر ----------------
    def show_city_wide_map_module(self):
        if not self._require_permission("city_map"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()

        if self.city_wide_map_window is None:
            self.city_wide_map_window = CityWideMapWindow(self.db)
            polish_widget_tree(self.city_wide_map_window)
            self.city_wide_map_window.back_requested.connect(self.back_from_city_wide_map_module)

        self._show_primary_window(self.city_wide_map_window)

    def back_from_city_wide_map_module(self):
        if self.city_wide_map_window:
            self.city_wide_map_window.hide()
        self.show_dashboard()

    # ---------------- مرکز عملیات و پیگیری ----------------
    def show_operations_center_module(self):
        if not self._require_permission("operations_center"):
            return
        if self.dashboard_window:
            self.dashboard_window.hide()
        if self.operations_center_window is None:
            self.operations_center_window = OperationsCenterWindow(self.db, self.current_user)
            polish_widget_tree(self.operations_center_window)
            self.operations_center_window.back_requested.connect(self.back_from_operations_center_module)
            self.operations_center_window.open_production_center_requested.connect(self.show_production_center_module)
        else:
            self.operations_center_window.refresh_all()
        self._show_primary_window(self.operations_center_window)

    def back_from_operations_center_module(self):
        if self.operations_center_window:
            self.operations_center_window.hide()
        self.show_dashboard()

    def restart_application(self):
        """
        پس از ریست سیستم یا بازگردانی بکاپ، دیتابیس ممکن است به‌کلی عوض شده باشد
        (فایل جایگزین شده یا داده‌ها پاک شده‌اند)، بنابراین تمام پنجره‌های ماژول‌ها
        را از بین می‌بریم تا در باز شدن بعدی، با داده و اتصال دیتابیس تازه ساخته شوند.
        همچنین کاربر برای امنیت مجدداً به صفحه ورود بازگردانده می‌شود.
        """
        for window_attr in ("blocking_window", "council_window", "priority_window",
                             "actions_window", "reports_window", "system_settings_window",
                             "city_wide_map_window", "neighborhood_management_window", "correspondence_window", "approval_templates_window",
                     "management_calendar_window", "project_control_window", "production_center_window", "operations_center_window", "client_management_window", "messaging_window", "dashboard_window"):
            window = getattr(self, window_attr, None)
            if window is not None:
                window.hide()
                window.deleteLater()
                setattr(self, window_attr, None)

        # اتصال قبلی به فایل دیتابیس را می‌بندیم و یک اتصال تازه باز می‌کنیم
        # (مهم است چون در حالت «بازگردانی بکاپ»، خود فایل دیتابیس جایگزین شده است)
        try:
            self.db.close()
        except Exception:
            pass
        self.db = Database()
        self.current_user = None
        try:
            self.db.ensure_daily_backup(keep=14)
        except Exception:
            pass
        update_tile_server_database(self.db)

        self.login_window.db = self.db
        self.login_window.username_input.clear()
        self.login_window.password_input.clear()
        self.login_window.error_label.setText("")
        self.login_window.show()

    def _destroy_module_windows(self):
        for attr in ("blocking_window", "council_window", "priority_window", "actions_window",
                     "reports_window", "system_settings_window", "city_wide_map_window",
                     "neighborhood_management_window", "correspondence_window", "approval_templates_window",
                     "management_calendar_window", "project_control_window", "production_center_window", "operations_center_window", "client_management_window", "messaging_window", "dashboard_window"):
            window = getattr(self, attr, None)
            if window is not None:
                window.hide()
                window.deleteLater()
                setattr(self, attr, None)

    # ---------------- خروج از حساب ----------------
    def logout(self):
        try:
            self.db.log_action("logout", "user", (self.current_user or {}).get("id"))
        except Exception:
            pass
        self._destroy_module_windows()
        self.current_user = None
        self.db.set_current_user(None)
        self.login_window.username_input.clear()
        self.login_window.password_input.clear()
        self.login_window.error_label.setText("")
        self.login_window.show()

    def shutdown(self):
        """بستن کنترل‌شده سرور محلی و دیتابیس هنگام خروج برنامه."""
        try:
            stop_tile_server()
        finally:
            try:
                self.db.close()
            except Exception:
                pass
            try:
                cleanup_runtime_files(days=14)
            except Exception:
                pass
            if self.session_guard is not None:
                self.session_guard.mark_clean()


def main():
    configure_windows_process()
    migrate_legacy_runtime_data()
    configure_logging()
    install_exception_hook()
    session_guard = RuntimeSessionGuard()
    previous_unclean = session_guard.begin()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(get_icon("map", "navy"))
    app.setLayoutDirection(Qt.RightToLeft)
    apply_application_typography(app)
    app.setStyleSheet(MAIN_STYLESHEET)
    app.ui_polish_filter = UiPolishFilter(app)
    app.installEventFilter(app.ui_polish_filter)
    app.responsive_ui_filter = ResponsiveUiFilter(app)
    app.installEventFilter(app.responsive_ui_filter)
    app.jalali_display_filter = JalaliDisplayFilter(app)
    app.installEventFilter(app.jalali_display_filter)

    try:
        controller = AppController(session_guard=session_guard, previous_unclean=previous_unclean)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("fatal startup error")
        QMessageBox.critical(
            None, "خطای راه‌اندازی",
            f"سامانه راه‌اندازی نشد. اطلاعات اصلی دست‌نخورده باقی مانده است.\n\n{exc}\n\nمسیر داده‌ها: {get_data_dir()}"
        )
        session_guard.mark_clean()
        return 2
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
