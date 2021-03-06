from django.conf.urls import patterns, url
from service import views

urlpatterns = patterns('',
  url(r'^$', views.ServiceDataSourceList.as_view(), name='service_data_sources_list'),
  url(r'^(?P<pk>\d+)/$', views.ServiceDataSourceDetail.as_view(), name='service_data_source_detail'),
  url(r'^new/$', views.ServiceDataSourceCreate.as_view(), name='service_data_source_new'),
  url(r'^(?P<pk>\d+)/edit/$', views.ServiceDataSourceUpdate.as_view(), name='service_data_source_edit'),
  url(r'^(?P<pk>\d+)/delete/$', views.ServiceDataSourceDelete.as_view(), name='service_data_source_delete'),
  url(r'^ServiceDataSourcelist/', views.ServiceDataSourceListingTable.as_view(), name='ServiceDataSourceListingTable'),
)
