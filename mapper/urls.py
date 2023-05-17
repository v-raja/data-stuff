from django.urls import path

from mapper import views

urlpatterns = [
    path("<int:schema_id>/mapper/", views.upload_files, name="upload_files"),
    # path('mapping_correction/', views.mapping_correction, name='mapping_correction'),
    path('<int:schema_id>/mapping_plan/', views.mapping_correction_form, name='mapping_correction'),
    path('<int:schema_id>/generate_file/', views.generate_file, name='generate_file'),
    path("create_schema/", views.create_schema, name="create_schema"),
    path('save_schema/', views.save_schema, name='save_schema'),
    path('data_quality/<int:schema_id>/', views.data_quality, name='data_quality'),
    path('', views.schema_list, name='schema_list'),
]