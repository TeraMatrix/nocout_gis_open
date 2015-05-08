# coding=utf-8
from django.conf.urls import patterns, url
from performance import views
from performance.views import GetServiceTypePerformanceData, \
    GetServiceStatus, DeviceServiceDetail, ServiceDataSourceListing, \
    ServiceDataSourceHeaders

from django.views.decorators.cache import cache_page

urlpatterns = patterns('',
                       url(
                          r'^(?P<page_type>\w+)_live/$',
                          views.LivePerformance.as_view(),
                          name='performance_listing_url'
                        ),
                       url(r'^liveperformancelistingtable/$',
                           views.LivePerformanceListing.as_view(),
                           name='LivePerformanceListing'
                       ),
                       url(r'^(?P<page_type>\w+)_live/(?P<device_id>\w+)/$',
                           views.GetPerfomance.as_view(),
                           name='SingleDevicePerf'
                       ),
                       url(r'^performance_dashboard/$',
                           views.PerformanceDashboard.as_view()
                       ),
                       url(r'^sector_dashboard/$',
                           views.SectorDashboard.as_view(),
                          name='spotDashboard'
                       ),
                       url(r'^sector_dashboard/listing/$',
                          views.SectorDashboardListing.as_view(),
                          name='spotDashboardListing'
                       ),
                       url(r'^get_inventory_device_status/(?P<page_type>\w+)/device/(?P<device_id>\d+)/$',
                           cache_page(60 * 60)(views.InventoryDeviceStatus.as_view()),
                           name='DeviceStatusUrl'
                       ),
                       url(r'^get_inventory_service_data_sources/device/(?P<device_id>\d+)/$',
                           views.InventoryDeviceServiceDataSource.as_view(), name='get_service_data_source_url'),
                       url(
                           r'^service/(?P<service_name>\w+)/service_data_source/(?P<service_data_source_type>\w+)/device/(?P<device_id>\d+)$',
                           GetServiceTypePerformanceData.as_view(),
                           name='GetServiceTypePerformanceData'
                       ),
                       url(
                           r'^headers/single_perf_page/$', ServiceDataSourceHeaders.as_view(), name='ServiceDataSourceHeaders'
                       ),
                       url(
                           r'^listing/service/(?P<service_name>\w+)/service_data_source/(?P<service_data_source_type>\w+)/device/(?P<device_id>\d+)$',
                           ServiceDataSourceListing.as_view(),
                           name='ServiceDataSourceListing'
                       ),
                       url(
                           r'^servicestatus/(?P<service_name>\w+)/service_data_source/(?P<service_data_source_type>\w+)/device/(?P<device_id>\d+)/$',
                           cache_page(60 * 2)(GetServiceStatus.as_view()),
                           name='GetServiceStatus'
                       ),
                       url(
                           r'^servicedetail/(?P<service_name>\w+)/device/(?P<device_id>\d+)',
                           DeviceServiceDetail.as_view(),
                           name='DeviceServiceDetail'
                       )
)