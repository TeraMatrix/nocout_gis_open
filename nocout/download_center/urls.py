from django.conf.urls import patterns, url
from download_center import views

urlpatterns = patterns('',
    url(r'^inventory/(?P<page_type>\w+)/$', views.DownloadCenter.as_view(), name='InventoryDownloadCenter'),
	url(r'^downloadcenterlistingtable/$', views.DownloadCenterListing.as_view(), name='DownloadCenterListing'),
	url(r'^delete/(?P<pk>\d+)$', views.DownloadCenterReportDelete.as_view(), name='report_delete'),
	# url(r'^citycharter/(?P<tech_name>\w+)/$', views.CityCharterReportInit.as_view(), name='CityCharterReports'),
	url(
		r'^citycharter/(?P<tech_name>\w+)/listing/(?P<is_data_limited>\w+)/$',
		views.CityCharterReportListing.as_view(),
		name='CityCharterReportListing'
	)
)
