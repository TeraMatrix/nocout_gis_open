from django.conf.urls import patterns, url

from dashboard import views


urlpatterns = patterns('',
    url(r'^settings/$', views.DashbaordSettingsListView.as_view(), name='dashboard-settings'),
    url(r'^settings/table/$', views.DashbaordSettingsListingTable.as_view(), name='dashboard-settings-table'),
    url(r'^settings/new/$', views.DashbaordSettingsCreateView.as_view(), name='dashboard-settings-new'),
    url(r'^settings/(?P<pk>\d+)/$', views.DashbaordSettingsDetailView.as_view(), name='dashboard-settings-detail'),
    url(r'^settings/(?P<pk>\d+)/edit/$', views.DashbaordSettingsUpdateView.as_view(), name='dashboard-settings-update'),
    url(r'^settings/(?P<pk>\d+)/delete/$', views.DashbaordSettingsDeleteView.as_view(), name='dashboard-settings-delete'),

    url(r'^rf-performance/wimax/$', views.WiMAX_Performance_Dashboard.as_view(), name='dashboard-rf-performance-wimax'),
    url(r'^rf-performance/pmp/$', views.PMP_Performance_Dashboard.as_view(), name='dashboard-rf-performance-pmp'),
    url(r'^rf-performance/ptp/$', views.PTP_Performance_Dashboard.as_view(), name='dashboard-rf-performance-ptp'),
    url(r'^rf-performance/ptp-bh/$', views.PTPBH_Performance_Dashboard.as_view(), name='dashboard-rf-performance-ptp-bh'),

    url(r'^mfr-dfr-reports/$', views.MFRDFRReportsListView.as_view(), name='mfr-dfr-reports-list'),
    url(r'^mfr-dfr-reports/table/$', views.MFRDFRReportsListingTable.as_view(), name='mfr-dfr-reports-table'),
    url(r'^mfr-dfr-reports/upload/$', views.MFRDFRReportsCreateView.as_view(), name='mfr-dfr-reports-upload'),
    url(r'^mfr-dfr-reports/(?P<pk>\d+)/delete/$', views.MFRDFRReportsDeleteView.as_view(), name='mfr-dfr-reports-delete'),

    url(r'^dfr-processed-reports/$', views.DFRProcessedListView.as_view(), name='dfr-processed-reports-list'),
    url(r'^dfr-processed-reports/table/$', views.DFRProcessedListingTable.as_view(), name='dfr-processed-reports-table'),
    url(r'^dfr-processed-reports/(?P<pk>\d+)/download/$', views.dfr_processed_report_download, name='dfr-processed-reports-download'),

    url(r'^dfr-reports/$', views.DFRReportsListView.as_view(), name='dfr-reports-list'),
    url(r'^dfr-reports/table/$', views.DFRReportsListingTable.as_view(), name='dfr-reports-table'),
    url(r'^dfr-reports/(?P<pk>\d+)/delete/$', views.DFRReportsDeleteView.as_view(), name='dfr-reports-delete'),

    url(r'^mfr-reports/$', views.MFRReportsListView.as_view(), name='mfr-reports-list'),
    url(r'^mfr-reports/table/$', views.MFRReportsListingTable.as_view(), name='mfr-reports-table'),
    url(r'^mfr-reports/(?P<pk>\d+)/delete/$', views.MFRReportsDeleteView.as_view(), name='mfr-reports-delete'),

    url(r'^sector-capacity/pmp/$', views.PMP_Sector_Capacity.as_view(), name='sector-capacity-pmp'),
    url(r'^sector-capacity/wimax/$', views.WIMAX_Sector_Capacity.as_view(), name='sector-capacity-wimax'),
    url(r'^sector-opportunity/pmp/$', views.PMP_Sales_Opportunity.as_view(), name='sales-opportunity-pmp'),
)
