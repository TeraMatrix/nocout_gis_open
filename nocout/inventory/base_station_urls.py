from django.conf.urls import patterns, url
from inventory import views

urlpatterns = patterns('',
  url(r'^$', views.BaseStationList.as_view(), name='base_stations_list'),
  url(r'^(?P<pk>\d+)/$', views.BaseStationDetail.as_view(), name='base_station_detail'),
  url(r'^new/$', views.BaseStationCreate.as_view(), name='base_station_new'),
  url(r'^(?P<pk>\d+)/edit/$', views.BaseStationUpdate.as_view(), name='base_station_edit'),
  url(r'^(?P<pk>\d+)/delete/$', views.BaseStationDelete.as_view(), name='base_station_delete'),
  url(r'^BaseStationlistingtable/', views.BaseStationListingTable.as_view(), name='BaseStationListingTable'),
  url(r'^select2/elements/$', views.SelectBaseStationListView.as_view(), name='select2-base-station-elements'),
)
