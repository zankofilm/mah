# -*- coding: utf-8 -*-
"""
تست ویژگی جدید: دانلود کامل و حرفه‌ای نقشه شهر برای استفاده کاملاً
آفلاین با یک کلیک. قبل از این تغییر، کاربر باید خودش سطح زوم را تنظیم
می‌کرد (پیش‌فرض فقط تا زوم ۱۸ و از ۱۲ شروع می‌شد) که برای «تمام جزئیات»
کافی نبود. اکنون یک محدوده زوم ثابت و توصیه‌شده (۱۰ تا ۱۹، یعنی از نمای
کلی شهر تا جزئی‌ترین سطح خیابان) در یک‌جا تعریف شده و با یک دکمه مورد
استفاده قرار می‌گیرد.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tile_downloader import (
    estimate_tile_count,
    RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE,
    get_tile_range,
)


class RecommendedZoomRangeTests(unittest.TestCase):
    def test_range_starts_at_city_overview_level(self):
        self.assertEqual(min(RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE), 10)

    def test_range_reaches_maximum_street_level_detail(self):
        """۱۹ حداکثر سطح زومی است که OpenStreetMap raster tiles پشتیبانی
        می‌کند؛ این تضمین می‌کند دانلود واقعاً «تمام جزئیات» را شامل شود،
        نه فقط تا زوم ۱۸ که پیش‌فرض قبلی بود."""
        self.assertEqual(max(RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE), 19)

    def test_range_covers_all_intermediate_zoom_levels(self):
        levels = list(RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE)
        self.assertEqual(levels, list(range(10, 20)))
        self.assertEqual(len(levels), 10)


class FullCityEstimationTests(unittest.TestCase):
    """این تست‌ها منطق برآورد را که در main.py (on_estimate_full_city_download)
    استفاده می‌شود، مستقل از PyQt می‌سنجند."""

    # محدوده کوچک و ثابت برای تست سریع و قابل‌تکرار (نه وابسته به مرکز واقعی شهر)
    SAMPLE_BBOX = (34.79, 46.47, 34.83, 46.51)

    def test_estimate_returns_positive_tile_count_for_valid_bbox(self):
        min_lat, min_lon, max_lat, max_lon = self.SAMPLE_BBOX
        count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE)
        self.assertGreater(count, 0)

    def test_recommended_range_yields_more_tiles_than_old_default(self):
        """محدوده جدید (۱۰-۱۹) باید همیشه مساوی یا بیشتر از محدوده قدیمی
        پیش‌فرض (۱۲-۱۷) تایل بدهد — چون هم بازه وسیع‌تر است هم زوم بالاتر
        (جزئیات بیشتر) دارد."""
        min_lat, min_lon, max_lat, max_lon = self.SAMPLE_BBOX
        old_default_count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, range(12, 18))
        new_count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE)
        self.assertGreater(new_count, old_default_count)

    def test_estimated_size_is_within_a_reasonable_one_time_download_budget(self):
        """برای یک شهر کوچک/متوسط، حجم کل دانلود نباید به گیگابایت‌ها
        برسد (که عملاً غیرقابل استفاده می‌شد)؛ این محافظت اطمینان می‌دهد
        محدوده توصیه‌شده برای یک دانلود یک‌باره واقع‌بینانه باقی می‌ماند."""
        min_lat, min_lon, max_lat, max_lon = self.SAMPLE_BBOX
        count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE)
        approx_mb = count * 15 / 1024
        self.assertLess(approx_mb, 2048)  # زیر ۲ گیگابایت برای این نمونه محدوده کوچک

    def test_tile_range_is_deterministic_for_same_bbox_and_zoom(self):
        """اطمینان از این‌که محاسبه محدوده تایل، قطعی (deterministic) است —
        فراخوانی تکراری با ورودی یکسان باید همیشه همان نتیجه را بدهد،
        چون این پایه محاسبه برآورد و دانلود واقعی است."""
        min_lat, min_lon, max_lat, max_lon = self.SAMPLE_BBOX
        result1 = get_tile_range(min_lat, min_lon, max_lat, max_lon, 15)
        result2 = get_tile_range(min_lat, min_lon, max_lat, max_lon, 15)
        self.assertEqual(result1, result2)


if __name__ == "__main__":
    unittest.main()
