from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("clients/", views.clients, name="clients"),
    path("clients/<int:pk>/", views.client_detail, name="client"),
    path("clients/<int:pk>/profile/", views.profile, name="profile"),
    path("clients/<int:pk>/topics/<slug:slug>/", views.topic_detail, name="topic"),
    path("queue/", views.queue, name="queue"),
    path("doubts/<int:pk>/", views.doubt_detail, name="doubt"),
    path("pins/<int:pk>/", views.pin_detail, name="pin"),
    path("pins/<int:pk>/action/", views.action, name="action"),
    path("sources/", views.sources, name="sources"),
    path("sources/<int:pk>/", views.source_detail, name="source"),
    path("sources/<int:pk>/upload/", views.upload, name="upload"),
    path("sources/<int:pk>/evidence-check/", views.ai_review, name="ai_review"),
    path("activity/", views.activity, name="activity"),
    path("people/", views.people, name="people"),
]
