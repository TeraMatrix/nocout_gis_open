from django.conf.urls import patterns, url
from inventory import views

urlpatterns = patterns('',
  url(r'^$', views.SectorList.as_view(), name='sectors_list'),
  url(r'^(?P<pk>\d+)/$', views.SectorDetail.as_view(), name='sector_detail'),
  url(r'^new/$', views.SectorCreate.as_view(), name='sector_new'),
  url(r'^(?P<pk>\d+)/edit/$', views.SectorUpdate.as_view(), name='sector_edit'),
  url(r'^(?P<pk>\d+)/delete/$', views.SectorDelete.as_view(), name='sector_delete'),
  url(r'^Sectorlistingtable/', views.SectorListingTable.as_view(), name='SectorListingTable'),
  url(r'^select2/elements/$', views.SelectSectorListView.as_view(), name='select2-sector-elements'),
)
