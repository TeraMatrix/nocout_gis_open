from django.conf.urls import patterns, url
from inventory import views

urlpatterns = patterns('',
  url(r'^$', views.CircuitList.as_view(), name='circuits_list'),
  url(r'^(?P<pk>\d+)$', views.CircuitDetail.as_view(), name='circuit_detail'),
  url(r'^new/$', views.CircuitCreate.as_view(), name='circuit_new'),
  url(r'^edit/(?P<pk>\d+)$', views.CircuitUpdate.as_view(), name='circuit_edit'),
  url(r'^delete/(?P<pk>\d+)$', views.CircuitDelete.as_view(), name='circuit_delete'),
  url(r'^Circuitlistingtable/', views.CircuitListingTable.as_view(), name='CircuitListingTable'),
  url(r'^l2_reports/(?P<circuit_id>\d+)/$', views.CircuitL2Report_Init.as_view(), name='circuit_l2_report'),
  url(r'^L2listingtable/(?P<circuit_id>\d+)$', views.L2ReportListingTable.as_view(), name='L2ReportListingTable'),
  url(r'^(?P<circuit_id>\d+)/l2_reports/create$', views.CircuitL2ReportCreate.as_view(), name='circuit_l2_report_create'),
  # url(r'^(?P<circuit_id>\d+)/l2_reports/delete(?P<l2_id>\d+)$', views.CircuitL2ReportDelete.as_view(), name='circuit_l2_report_delete'),
)